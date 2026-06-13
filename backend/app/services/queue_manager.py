"""
Queue Manager for eBay Draft Commander.

Orchestration layer: threading, DB persistence, Socket.IO events, pause/resume.
For the data model (JobStatus, QueueJob, resolve_thumbnail), see queue_job.py.

All three are re-exported here so existing imports keep working:
    from backend.app.services.queue_manager import QueueManager, QueueJob, JobStatus
"""
import uuid
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Callable, Dict, Any
from backend.app.core.logger import get_logger
from backend.app.core.paths import get_data_dir
from backend.app.core.exceptions import NeedsReviewException

# Re-export data model so existing imports don't break
from backend.app.services.queue_job import JobStatus, QueueJob, resolve_thumbnail  # noqa: F401


class QueueManager:
    """
    Manages batch processing queue for eBay listings.
    
    Features:
    - Add folders individually or in batch
    - Background processing with threading
    - Pause/resume capability
    - State persistence to JSON
    - Progress callbacks for UI updates
    """
    
    def __init__(self, base_path: Path = None):
        # Initialize logger first
        self.logger = get_logger('queue_manager', level='DEBUG')

        self.base_path = base_path or get_data_dir().parent
        # base_path must fully isolate storage (tests rely on this for DB isolation)
        self.data_path = (Path(base_path) / "data") if base_path else get_data_dir()
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_path / "commander.db"
        
        from backend.app.core.database import init_db, JobModel
        self.SessionFactory = init_db(self.db_path)
        self.JobModel = JobModel
        
        # Auto-Migration: Ensure scheduled_time exists
        self._ensure_schema()

        self._processing = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Callbacks for UI updates
        self.on_job_start: Optional[Callable[[QueueJob], None]] = None
        self.on_job_complete: Optional[Callable[[QueueJob], None]] = None
        self.on_job_error: Optional[Callable[[QueueJob], None]] = None
        self.on_job_added: Optional[Callable[[QueueJob], None]] = None
        self.on_queue_complete: Optional[Callable[[], None]] = None
        self.on_progress: Optional[Callable[[int, int], None]] = None  # (current, total)
        
        # Socket.IO instance (injected from create_app)
        self.socketio = None

        # Load state and start background threads
        self._init_background_services()

        # Batch statistics
        self._batch_stats = {
            'active': False,
            'succeeded': 0,
            'failed': 0,
            'total_value': 0.0,
            'item_times': [],
            'start_time': None
        }
        
    def _reset_batch_stats(self):
        """Reset statistics for a new batch run"""
        self._batch_stats = {
            'active': True,
            'succeeded': 0,
            'failed': 0,
            'total_value': 0.0,
            'item_times': [],
            'start_time': time.time()
        }
        
    def _ensure_schema(self):
        """Simple migration helper to add columns if missing"""
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(jobs)")
            columns = [info[1] for info in cursor.fetchall()]

            if 'scheduled_time' not in columns:
                self.logger.info("Migrating DB: Adding scheduled_time column...")
                cursor.execute("ALTER TABLE jobs ADD COLUMN scheduled_time TIMESTAMP")

            if 'thumbnail_name' not in columns:
                self.logger.info("Migrating DB: Adding thumbnail_name column...")
                cursor.execute("ALTER TABLE jobs ADD COLUMN thumbnail_name VARCHAR(255)")

            if 'confidence_score' not in columns:
                self.logger.info("Migrating DB: Adding confidence_score column...")
                cursor.execute("ALTER TABLE jobs ADD COLUMN confidence_score FLOAT")

            if 'batch_id' not in columns:
                self.logger.info("Migrating DB: Adding batch_id column...")
                cursor.execute("ALTER TABLE jobs ADD COLUMN batch_id VARCHAR(50)")

            # Taxonomy cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS taxonomy_cache (
                    query_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

            # Category corrections table (human feedback loop)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS category_corrections (
                    title_hash TEXT PRIMARY KEY,
                    original_title TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    category_name TEXT DEFAULT '',
                    use_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.warning(f"Schema migration warning: {e}")

        # Always backfill thumbnail_name for jobs that have NULL
        self._backfill_thumbnails()

    def _backfill_thumbnails(self):
        """One-time backfill: resolve thumbnail_name for jobs that have NULL."""
        session = self.SessionFactory()
        try:
            jobs_missing = session.query(self.JobModel).filter(
                self.JobModel.thumbnail_name.is_(None)
            ).all()
            if not jobs_missing:
                return
            count = 0
            for db_job in jobs_missing:
                thumb = resolve_thumbnail(db_job.folder_path)
                if thumb:
                    db_job.thumbnail_name = thumb
                    count += 1
            if count:
                session.commit()
                self.logger.info(f"Backfilled thumbnail_name for {count}/{len(jobs_missing)} jobs")
        except Exception as e:
            session.rollback()
            self.logger.warning(f"Thumbnail backfill warning: {e}")
        finally:
            session.close()

    def _init_background_services(self):
        """Start background threads and load persisted state. Called from __init__."""
        # Load any persisted state
        self.load_state()

        # Track current job
        self._current_job: Optional[QueueJob] = None

        # Start Token Maintenance Thread (Heartbeat)
        self._token_thread = threading.Thread(target=self._token_maintainer, daemon=True)
        self._token_thread.start()

        # Start Inbox Watcher Thread — respect INBOX_PATH env var if set
        import os
        custom_inbox = os.environ.get('INBOX_PATH')
        self.inbox_path = Path(custom_inbox) if custom_inbox else self.base_path / "inbox"
        self._watcher_thread = threading.Thread(target=self._watch_inbox, daemon=True)
        self._watcher_thread.start()

    @property
    def current_job(self) -> Optional[QueueJob]:
        """Get the currently processing job"""
        return self._current_job

    def emit_event(self, event: str, data: Any):
        """Helper to emit events to frontend via Socket.IO (thread-safe)"""
        if self.socketio:
            try:
                self.socketio.emit(event, data)
            except Exception as e:
                self.logger.warning(f"Socket.IO emit failed for '{event}': {e}")

    def _token_maintainer(self):
        """Background thread to keep eBay token alive"""
        self.logger.info("Token Maintenance Heartbeat started")
        from backend.app.core.token_manager import get_token_manager

        while True:
            try:
                # Sleep for 60 minutes
                time.sleep(3600)

                self.logger.info("Running scheduled token refresh...")
                tm = get_token_manager()
                if tm.force_refresh():
                    self.logger.info("Token refreshed successfully (Background)")
                else:
                    self.logger.warning("Background token refresh failed")

            except Exception as e:
                self.logger.error(f"Token maintenance error: {e}")
                time.sleep(300) # Retry sooner on error
    # ... existing methods ...

    def add_folder(self, folder_path: str, metadata: dict = None, batch_id: str = None) -> QueueJob:
        """
        Add a folder to the queue.
        
        Args:
            folder_path: Path to the item folder
            metadata: Optional job metadata (e.g. condition)
            batch_id: Optional ID to group this job into a batch
            
        Returns:
            The created QueueJob
        """
        path_obj = Path(folder_path)
        job_id = str(uuid.uuid4())[:8]
        
        job = QueueJob(
            id=job_id,
            folder_path=str(path_obj),
            folder_name=path_obj.name,
            batch_id=batch_id
        )
        if metadata:
            job.job_metadata.update(metadata)
            if 'condition' in metadata:
                job.condition = metadata['condition']
        
        # Resolve thumbnail once at creation
        job.thumbnail_name = resolve_thumbnail(job.folder_path)
        
        session = self.SessionFactory()
        try:
            db_job = self._queue_job_to_db(job)
            session.add(db_job)
            session.commit()
            
            # Re-read to ensure everything is synced
            job = self._db_to_queue_job(db_job)
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to add job to database: {e}")
            raise
        finally:
            session.close()
            
        if self.on_job_added:
            self.on_job_added(job)
            
        return job


    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Update a job's fields directly in the database.

        This is the single source of truth for job mutations.
        Handles type conversion for datetime fields, status enums, and JSON properties.

        Args:
            job_id: The job ID to update
            updates: Dict of field names to new values. Supports:
                - Simple fields: user_title, user_price, user_description, user_condition,
                  price, listing_id, offer_id, error_type, error_message, attempts,
                  confidence_score, batch_id
                - JSON fields: item_specifics, ai_data, job_metadata, timing
                - DateTime fields: scheduled_time, started_at, completed_at (accepts ISO strings)
                - Status: status (accepts JobStatus enum or string)

        Returns:
            True if update succeeded, False otherwise
        """
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(id=job_id).first()
            if not db_job:
                self.logger.warning(f"update_job: job {job_id} not found")
                return False

            # Fields that need datetime conversion (ISO string → datetime object)
            datetime_fields = {'scheduled_time', 'started_at', 'completed_at'}

            for field_name, value in updates.items():
                # Handle status enum → string
                if field_name == 'status':
                    if isinstance(value, JobStatus):
                        value = value.value
                    db_job.status = value
                # Handle datetime fields (accept ISO strings, convert to datetime)
                elif field_name in datetime_fields:
                    if value and isinstance(value, str):
                        db_job.__setattr__(field_name, datetime.fromisoformat(value.replace('Z', '+00:00')))
                    elif value is None:
                        setattr(db_job, field_name, None)
                    else:
                        setattr(db_job, field_name, value)
                # JSON property fields (ai_data, item_specifics, timing, job_metadata)
                # These have @property setters that handle json.dumps
                elif field_name in ('ai_data', 'item_specifics', 'timing', 'job_metadata'):
                    setattr(db_job, field_name, value)
                # Simple scalar fields
                elif hasattr(db_job, field_name):
                    setattr(db_job, field_name, value)
                else:
                    self.logger.warning(f"update_job: unknown field '{field_name}' for job {job_id}")

            session.commit()

            # Emit update event for real-time UI sync
            updated_job = self._db_to_queue_job(db_job)
            self.emit_event('job_update', updated_job.to_dict())

            return True
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to update job {job_id}: {e}", exc_info=True)
            return False
        finally:
            session.close()
            
    # ... existing methods ...

    def load_state(self):
        """Recover from unclean shutdown: reset any stuck 'processing' jobs back to 'pending'."""
        session = self.SessionFactory()
        try:
            # Reset any jobs that were processing when we closed
            stuck_count = session.query(self.JobModel).filter_by(
                status=JobStatus.PROCESSING.value
            ).update({'status': JobStatus.PENDING.value}, synchronize_session=False)

            if stuck_count > 0:
                session.commit()
                self.logger.info(f"Reset {stuck_count} stuck 'processing' job(s) to 'pending'")

            total = session.query(self.JobModel).count()
            self.logger.info(f"Database contains {total} jobs")

        except Exception as e:
            self.logger.error(f"Error during startup recovery: {e}")
        finally:
            session.close()

    def get_all_jobs(self) -> List[QueueJob]:
        """Fetch all jobs directly from DB"""
        session = self.SessionFactory()
        try:
            db_jobs = session.query(self.JobModel).all()
            return [self._db_to_queue_job(j) for j in db_jobs]
        except Exception as e:
            self.logger.error(f"Error getting jobs from DB: {e}")
            return []
        finally:
            session.close()

    def _queue_job_to_db(self, job: QueueJob):
        """Convert a QueueJob to a JobModel instance."""
        return self.JobModel(
            id=job.id,
            folder_path=job.folder_path,
            folder_name=job.folder_name,
            status=job.status.value,
            listing_id=job.listing_id,
            offer_id=job.offer_id,
            price=job.price,
            title=job.title,
            condition=job.condition,
            user_title=job.user_title,
            user_price=job.user_price,
            user_description=job.user_description,
            user_condition=job.user_condition,
            ai_data=job.ai_data,
            item_specifics=job.item_specifics,
            error_type=job.error_type,
            error_message=job.error_message,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            created_at=datetime.fromisoformat(job.created_at),
            started_at=datetime.fromisoformat(job.started_at) if job.started_at else None,
            completed_at=datetime.fromisoformat(job.completed_at) if job.completed_at else None,
            scheduled_time=datetime.fromisoformat(job.scheduled_time) if job.scheduled_time else None,
            timing=job.timing,
            job_metadata=job.job_metadata,
            thumbnail_name=job.thumbnail_name,
            confidence_score=job.confidence_score,
            batch_id=job.batch_id
        )

    def _db_to_queue_job(self, db_j) -> QueueJob:
        """Convert a JobModel to a QueueJob."""
        return QueueJob(
            id=db_j.id,
            folder_path=db_j.folder_path,
            folder_name=db_j.folder_name,
            status=JobStatus(db_j.status),
            listing_id=db_j.listing_id,
            offer_id=db_j.offer_id,
            price=db_j.price,
            title=db_j.title,
            condition=db_j.condition,
            user_title=db_j.user_title,
            user_price=db_j.user_price,
            user_description=db_j.user_description,
            user_condition=db_j.user_condition,
            ai_data=db_j.ai_data or {},
            item_specifics=db_j.item_specifics or {},
            error_type=db_j.error_type,
            error_message=db_j.error_message,
            attempts=db_j.attempts,
            max_attempts=db_j.max_attempts,
            created_at=db_j.created_at.isoformat() if db_j.created_at else datetime.now().isoformat(),
            started_at=db_j.started_at.isoformat() if db_j.started_at else None,
            completed_at=db_j.completed_at.isoformat() if db_j.completed_at else None,
            scheduled_time=db_j.scheduled_time.isoformat() if db_j.scheduled_time else None,
            timing=db_j.timing or {},
            job_metadata=db_j.job_metadata or {},
            thumbnail_name=getattr(db_j, 'thumbnail_name', None),
            confidence_score=db_j.confidence_score,
        )

    def _watch_inbox(self):
        """Background thread to watch for new items in inbox"""
        self.logger.info(f"Inbox Watcher started on: {self.inbox_path}")
        # Import here to avoid circular dependency
        from backend.app.services.scanner_service import ScannerService
        scanner = ScannerService(self.inbox_path)

        while True:
            try:
                time.sleep(10) # Check every 10 seconds

                if not self.inbox_path.exists():
                    continue

                result = scanner.scan_inbox(self)
                
                if result.get('added', 0) > 0:
                    self.logger.info(f"Auto-detected {result['added']} new job(s) from inbox")
                    # If we added jobs and aren't processing, start processing
                    if not self.is_processing() and not self.is_paused():
                         self.start_processing()
                         
            except Exception as e:
                self.logger.error(f"Inbox watcher error: {e}")
                time.sleep(60) # Back off on error

    def set_app(self, app):
        """Set Flask app instance for context pushing"""
        self.app = app

    def _process_queue(self):
        """Background worker to process jobs sequentially"""
        while True:
            try:
                # Check for pause (thread-safe)
                with self._lock:
                    paused = self._paused
                if paused:
                    time.sleep(0.1)
                    continue

                # Get next pending job
                job = self._get_next_pending()
                if not job:
                    # No pending jobs — check if we should exit
                    stats = self.get_stats()
                    if stats['pending'] == 0 and stats['processing'] == 0:
                        # Batch complete! Emit stats before breaking
                        if self._batch_stats['active']:
                            duration = time.time() - self._batch_stats['start_time']
                            avg_time = sum(self._batch_stats['item_times']) / len(self._batch_stats['item_times']) if self._batch_stats['item_times'] else 0
                            
                            summary = {
                                'succeeded': self._batch_stats['succeeded'],
                                'failed': self._batch_stats['failed'],
                                'total_value': round(self._batch_stats['total_value'], 2),
                                'avg_time': round(avg_time, 2),
                                'total_duration': round(duration, 2)
                            }
                            self.logger.info(f"Batch Processing Complete: {summary}")
                            self.emit_event('batch_complete', summary)
                            self._batch_stats['active'] = False
                            
                        break  # Queue is done
                    time.sleep(1)
                    continue

                # Process it
                self._current_job = job
                if self.app:
                    with self.app.app_context():
                        self._process_job(job)
                else:
                    self.logger.warning("No Flask App context available for QueueManager thread!")
                    self._process_job(job)
                self._current_job = None

                # Update progress
                stats = self.get_stats()
                done = stats['completed'] + stats['failed'] + stats['skipped']
                if self.on_progress:
                    self.on_progress(done, stats['total'])
            except Exception as e:
                self.logger.error(f"Queue worker error (will retry): {e}", exc_info=True)
                self._current_job = None
                time.sleep(5)  # Back off before retrying

        with self._lock:
            self._processing = False
        if self.on_queue_complete:
            self.on_queue_complete()
        
    def add_batch(self, folder_paths: List[str]) -> List[QueueJob]:
        """Add multiple folders to the queue"""
        jobs = []
        for path in folder_paths:
            jobs.append(self.add_folder(path))
        return jobs
    
    def _delete_folder(self, folder_path: str) -> bool:
        """Safely delete a job's inbox folder from disk."""
        try:
            p = Path(folder_path)
            if p.exists() and p.is_dir():
                shutil.rmtree(p)
                self.logger.info(f"Deleted folder: {p}")
                return True
        except Exception as e:
            self.logger.warning(f"Failed to delete folder {folder_path}: {e}")
        return False

    def update_thumbnail(self, job_id: str, thumb_name: str):
        """Cache a resolved thumbnail filename for a job."""
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(id=job_id).first()
            if db_job:
                db_job.thumbnail_name = thumb_name
                session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()

    def remove_job(self, job_id: str, delete_folder: bool = False) -> bool:
        """Remove a job from the queue. Allowed for any state EXCEPT a job that
        is actively processing — deleting mid-run would orphan the worker
        thread and its in-flight eBay/AI calls. All other states (pending,
        failed, skipped, completed, pending_review, needs_review, scheduled,
        paused) are user-discardable from the dashboard."""
        # Never delete the job the worker thread is currently running.
        current = self._current_job
        if current and current.id == job_id:
            self.logger.warning(f"Refusing to remove actively-processing job {job_id}")
            return False
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(id=job_id).first()
            if db_job and db_job.status != JobStatus.PROCESSING.value:
                folder_path = db_job.folder_path
                session.delete(db_job)
                session.commit()
                if delete_folder and folder_path:
                    self._delete_folder(folder_path)
                return True
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to remove job from database: {e}")
        finally:
            session.close()
        return False
    
    def skip_job(self, job_id: str) -> bool:
        """Skip a pending job"""
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(id=job_id).first()
            if db_job and db_job.status == JobStatus.PENDING.value:
                db_job.status = JobStatus.SKIPPED.value
                session.commit()
                return True
        except Exception as e:
            session.rollback()
        finally:
            session.close()
        return False
    
    def clear_completed(self, delete_folders: bool = False) -> dict:
        """Remove all completed and skipped jobs from the queue.
        Returns {'count': N, 'folders_deleted': M}."""
        session = self.SessionFactory()
        try:
            jobs = session.query(self.JobModel).filter(
                self.JobModel.status.in_([JobStatus.COMPLETED.value, JobStatus.SKIPPED.value])
            ).all()
            count = len(jobs)
            folders_deleted = 0
            if delete_folders:
                folder_paths = [db_job.folder_path for db_job in jobs if db_job.folder_path]
                if folder_paths:
                    with ThreadPoolExecutor(max_workers=min(len(folder_paths), 10)) as executor:
                        results = list(executor.map(self._delete_folder, folder_paths))
                    folders_deleted = sum(1 for r in results if r)

            for db_job in jobs:
                session.delete(db_job)
            session.commit()
            return {'count': count, 'folders_deleted': folders_deleted}
        except Exception as e:
            session.rollback()
            return {'count': 0, 'folders_deleted': 0}
        finally:
            session.close()

    def clear_failed(self, delete_folders: bool = False) -> dict:
        """Remove all failed jobs from the queue.
        Returns {'count': N, 'folders_deleted': M}."""
        session = self.SessionFactory()
        try:
            jobs = session.query(self.JobModel).filter(
                self.JobModel.status == JobStatus.FAILED.value
            ).all()
            count = len(jobs)
            folders_deleted = 0
            if delete_folders:
                folder_paths = [db_job.folder_path for db_job in jobs if db_job.folder_path]
                if folder_paths:
                    with ThreadPoolExecutor(max_workers=min(len(folder_paths), 10)) as executor:
                        results = list(executor.map(self._delete_folder, folder_paths))
                    folders_deleted = sum(1 for r in results if r)
            for db_job in jobs:
                session.delete(db_job)
            session.commit()
            return {'count': count, 'folders_deleted': folders_deleted}
        except Exception as e:
            session.rollback()
            return {'count': 0, 'folders_deleted': 0}
        finally:
            session.close()
    
    def purge_missing_folders(self) -> dict:
        """Remove jobs whose source folder no longer exists on disk (stale
        test rows, manually deleted inbox folders). Active jobs are exempt —
        a folder vanishing mid-processing is the pipeline's problem to report,
        not silent row deletion. Returns {'count': N}."""
        session = self.SessionFactory()
        try:
            jobs = session.query(self.JobModel).filter(
                self.JobModel.status != JobStatus.PROCESSING.value
            ).all()
            stale = [j for j in jobs if not j.folder_path or not Path(j.folder_path).exists()]
            for db_job in stale:
                session.delete(db_job)
            session.commit()
            return {'count': len(stale)}
        except Exception:
            session.rollback()
            return {'count': 0}
        finally:
            session.close()

    def clear_all(self):
        """Clear all jobs from the queue"""
        session = self.SessionFactory()
        try:
            session.query(self.JobModel).delete()
            session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()
    
    def get_pending_jobs(self) -> List[QueueJob]:
        """Get all pending jobs"""
        session = self.SessionFactory()
        try:
            db_jobs = session.query(self.JobModel).filter_by(status=JobStatus.PENDING.value).all()
            return [self._db_to_queue_job(j) for j in db_jobs]
        finally:
            session.close()
    
    def get_failed_jobs(self) -> List[QueueJob]:
        """Get all failed jobs"""
        session = self.SessionFactory()
        try:
            db_jobs = session.query(self.JobModel).filter_by(status=JobStatus.FAILED.value).all()
            return [self._db_to_queue_job(j) for j in db_jobs]
        finally:
            session.close()
    
    def get_stats(self) -> dict:
        """Get queue statistics directly from DB"""
        session = self.SessionFactory()
        try:
            from sqlalchemy import func
            results = session.query(
                self.JobModel.status, 
                func.count(self.JobModel.id)
            ).group_by(self.JobModel.status).all()
            
            stats = {
                'total': 0, 'pending': 0, 'processing': 0, 
                'completed': 0, 'failed': 0, 'skipped': 0
            }
            
            for status, count in results:
                if status in stats:
                    stats[status] = count
                stats['total'] += count
                
            return stats
        finally:
            session.close()
    
    def start_processing(self):
        """Start processing the queue in background thread"""
        with self._lock:
            if self._processing:
                return
            self._processing = True
            self._paused = False
            self._reset_batch_stats()
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()

    def pause(self):
        """Pause processing after current job completes"""
        with self._lock:
            self._paused = True

    def resume(self):
        """Resume processing"""
        with self._lock:
            if self._paused:
                self._paused = False
                should_start = not self._processing
            else:
                should_start = False
        if should_start:
            self.start_processing()

    def is_processing(self) -> bool:
        """Check if queue is actively processing"""
        with self._lock:
            return self._processing and not self._paused

    def is_paused(self) -> bool:
        """Check if queue is paused"""
        with self._lock:
            return self._paused
    
    def log_status(self, job_id: str, message: str, level: str = 'info'):
        """Broadcast a micro-log update for a specific job"""
        self.logger.info(f"[{job_id}] {message}")
        self.emit_event('job_log', {
            'job_id': job_id,
            'message': message,
            'level': level,
            'timestamp': datetime.now().isoformat()
        })
    
    def retry_failed(self) -> int:
        """Reset all failed jobs to pending"""
        session = self.SessionFactory()
        try:
            # Note: We rely on the frontend to refresh the view
            # In a DB-only system, we just update the rows directly
            updated_count = session.query(self.JobModel).filter(
                self.JobModel.status == JobStatus.FAILED.value,
                self.JobModel.attempts < self.JobModel.max_attempts
            ).update({
                'status': JobStatus.PENDING.value,
                'error_type': None,
                'error_message': None
            }, synchronize_session=False)
            
            if updated_count > 0:
                session.commit()
                self.logger.info(f"Retrying {updated_count} failed jobs")
            
            return updated_count
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to retry jobs in DB: {e}")
            return 0
        finally:
            session.close()
    
    def retry_job(self, job_id: str) -> bool:
        """Retry a specific failed job"""
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(id=job_id).first()
            valid_statuses = [JobStatus.FAILED.value, JobStatus.NEEDS_REVIEW.value, JobStatus.PENDING_REVIEW.value]
            if db_job and db_job.status in valid_statuses:
                db_job.status = JobStatus.PENDING.value
                db_job.error_type = None
                db_job.error_message = None
                db_job.attempts = 0
                session.commit()
                return True
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to retry job {job_id} in DB: {e}")
        finally:
            session.close()
            
        return False
    
    def _get_next_pending(self) -> Optional[QueueJob]:
        """Get next pending job from the database"""
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(status=JobStatus.PENDING.value).first()
            if db_job:
                return self._db_to_queue_job(db_job)
            return None
        finally:
            session.close()
    
    def _process_job(self, job: QueueJob):
        """Process a single job"""
        started_at = datetime.now().isoformat()
        job.status = JobStatus.PROCESSING
        job.started_at = started_at
        job.attempts += 1

        # Persist "processing" state immediately to DB
        self.update_job(job.id, {
            'status': JobStatus.PROCESSING,
            'started_at': started_at,
            'attempts': job.attempts,
        })
        self.log_status(job.id, "[START] Starting processing pipeline...")

        if self.on_job_start:
            self.on_job_start(job)

        try:
            start_time = time.time()
            self.log_status(job.id, "[SEARCH] Analyzing images with AI...")

            # Instantiate ProcessorService (Phase 3 Architecture)
            from backend.app.services.processor_service import ProcessorService
            processor = ProcessorService()

            # Create callback for logging
            def job_log_callback(msg, level='info'):
                self.log_status(job.id, msg, level)

            # Pass job object directly to processor
            result = processor.create_listing(job, log_callback=job_log_callback)

            elapsed = time.time() - start_time

            # Handle result
            if isinstance(result, dict):
                if result.get('status') == 'awaiting_condition':
                    job.status = JobStatus.AWAITING_CONDITION
                    job.title = result.get('title')
                    job.confidence_score = result.get('confidence_score')
                    job.timing = result.get('timing', {'total': elapsed})
                elif result.get('status') == 'pending_review':
                    # Routed to review queue (AUTO_PUBLISH=false, low confidence, or missing category)
                    job.status = JobStatus.PENDING_REVIEW
                    job.price = result.get('price')
                    job.title = result.get('title')
                    job.condition = result.get('condition')
                    job.confidence_score = result.get('confidence_score')
                    job.timing = result.get('timing', {'total': elapsed})
                elif result.get('success', False) or result.get('listing_id') or result.get('offer_id'):
                    # Use SCHEDULED status if listing was scheduled for future
                    if result.get('status') == 'Scheduled' and result.get('scheduled_time'):
                        job.status = JobStatus.SCHEDULED
                        job.scheduled_time = result.get('scheduled_time')
                    else:
                        job.status = JobStatus.COMPLETED
                    job.listing_id = result.get('listing_id')
                    job.offer_id = result.get('offer_id')
                    job.price = result.get('price')
                    job.title = result.get('title')
                    job.condition = result.get('condition')
                    job.timing = result.get('timing', {'total': elapsed})
                else:
                    job.status = JobStatus.FAILED
                    job.error_type = result.get('error_type', 'unknown')
                    job.error_message = result.get('error_message', str(result.get('error', 'Unknown error')))
            elif result:
                # Legacy: just a listing_id string
                job.status = JobStatus.COMPLETED
                job.listing_id = str(result)
                job.timing = {'total': elapsed}
            else:
                job.status = JobStatus.FAILED
                job.error_type = 'null_result'
                job.error_message = 'Processor returned None'

        except Exception as e:
            # Check if this is a NeedsReview exception from the processor service
            if isinstance(e, NeedsReviewException):
                self.log_status(job.id, f"[WARN] Needs Review: {str(e)}", "warning")
                job.status = JobStatus.NEEDS_REVIEW
                job.error_message = str(e)
                job.error_type = "needs_review"
                job.attempts = job.max_attempts
            else:
                job.status = JobStatus.FAILED
                job.error_type = type(e).__name__
                job.error_message = str(e)

        job.completed_at = datetime.now().isoformat()

        # Persist final result to database via update_job()
        self.update_job(job.id, {
            'status': job.status,
            'listing_id': job.listing_id,
            'offer_id': job.offer_id,
            'price': job.price,
            'title': job.title,
            'condition': job.condition,
            'confidence_score': job.confidence_score,
            'timing': job.timing,
            'error_type': job.error_type,
            'error_message': job.error_message,
            'attempts': job.attempts,
            'started_at': job.started_at,
            'completed_at': job.completed_at,
            'scheduled_time': job.scheduled_time,
            'job_metadata': job.job_metadata,
            'ai_data': job.ai_data,
            'item_specifics': job.item_specifics,
        })

        # Update batch stats
        if self._batch_stats['active']:
            self._batch_stats['item_times'].append(elapsed)
            if job.status == JobStatus.COMPLETED:
                self._batch_stats['succeeded'] += 1
                try:
                    price_str = str(job.price or "0").replace('$', '').replace(',', '')
                    self._batch_stats['total_value'] += float(price_str)
                except (ValueError, TypeError):
                    pass
            elif job.status == JobStatus.FAILED:
                self._batch_stats['failed'] += 1

        if job.status == JobStatus.COMPLETED:
            if self.on_job_complete:
                self.on_job_complete(job)
        else:
            if self.on_job_error:
                self.on_job_error(job)
    
    def get_job_by_id(self, job_id: str) -> Optional[QueueJob]:
        """Get a job by its ID"""
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(id=job_id).first()
            if db_job:
                return self._db_to_queue_job(db_job)
            return None
        finally:
            session.close()
    
    def get_job_by_folder(self, folder_name: str, folder_path: str = None) -> Optional[QueueJob]:
        """Get a job by folder path (preferred) or folder name."""
        session = self.SessionFactory()
        try:
            query = session.query(self.JobModel)
            if folder_path:
                db_job = query.filter_by(folder_path=folder_path).first()
            else:
                db_job = query.filter_by(folder_name=folder_name).first()
            if db_job:
                return self._db_to_queue_job(db_job)
        except Exception as e:
            logger.debug("Folder lookup failed for '%s': %s", folder_path or folder_name, e)
        finally:
            session.close()

        return None

    def get_batch_summary(self, batch_id: str) -> Dict[str, Any]:
        """Calculate summary statistics for a specific batch."""
        session = self.SessionFactory()
        try:
            db_jobs = session.query(self.JobModel).filter_by(batch_id=batch_id).all()
            if not db_jobs:
                return {
                    'batch_id': batch_id,
                    'total_processed': 0,
                    'succeeded': 0,
                    'failed': 0,
                    'total_value_listed': 0.0,
                    'average_processing_time_seconds': 0.0
                }
                
            jobs = [self._db_to_queue_job(db_job) for db_job in db_jobs]
            
            total = len(jobs)
            succeeded = [j for j in jobs if j.status == JobStatus.COMPLETED]
            failed = [j for j in jobs if j.status == JobStatus.FAILED]
            
            total_value = 0.0
            for j in succeeded:
                try:
                    price_str = str(j.price or "0").replace('$', '').replace(',', '')
                    total_value += float(price_str)
                except (ValueError, TypeError):
                    pass
            
            durations = []
            for j in jobs:
                if j.timing and 'total' in j.timing:
                    durations.append(j.timing['total'])
            
            avg_time = sum(durations) / len(durations) if durations else 0.0
            
            return {
                'batch_id': batch_id,
                'total_processed': total,
                'succeeded': len(succeeded),
                'failed': len(failed),
                'total_value_listed': round(total_value, 2),
                'average_processing_time_seconds': round(avg_time, 2)
            }
        finally:
            session.close()