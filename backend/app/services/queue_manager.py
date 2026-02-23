"""
Queue Manager for eBay Draft Commander
Handles batch job processing with state persistence, pause/resume, and error recovery.
"""
import json
import uuid
import threading
import time
from pathlib import Path
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Callable, Dict, Any
from backend.app.core.logger import get_logger
from backend.app.core.paths import get_data_dir


class JobStatus(Enum):
    """Status of a queue job"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"
    SCHEDULED = "scheduled"
    NEEDS_REVIEW = "needs_review"


@dataclass
class QueueJob:
    """Represents a single listing job in the queue"""
    id: str
    folder_path: str
    folder_name: str
    status: JobStatus = JobStatus.PENDING
    
    # Core Data
    listing_id: Optional[str] = None
    offer_id: Optional[str] = None
    price: Optional[str] = None
    
    # User Overrides
    user_title: Optional[str] = None
    user_price: Optional[str] = None
    user_description: Optional[str] = None
    user_condition: Optional[str] = None
    
    # Rich Data
    ai_data: Dict[str, Any] = field(default_factory=dict)
    item_specifics: Dict[str, Any] = field(default_factory=dict)
    
    # Error Handling
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    
    # Timing & Meta
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    scheduled_time: Optional[str] = None
    timing: Dict[str, float] = field(default_factory=dict)
    job_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.status == JobStatus.FAILED and self.attempts < self.max_attempts


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
        self.data_path = get_data_dir()
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
        self.on_queue_complete: Optional[Callable[[], None]] = None
        self.on_progress: Optional[Callable[[int, int], None]] = None  # (current, total)
        
        # Socket.IO instance (injected from create_app)
        self.socketio = None

        # Load state and start background threads
        self._init_background_services()
        
    def _ensure_schema(self):
        """Simple migration helper to add columns if missing"""
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Check if scheduled_time exists
            cursor.execute("PRAGMA table_info(jobs)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'scheduled_time' not in columns:
                self.logger.info("Migrating DB: Adding scheduled_time column...")
                cursor.execute("ALTER TABLE jobs ADD COLUMN scheduled_time TIMESTAMP")
                conn.commit()
            conn.close()
        except Exception as e:
            self.logger.warning(f"Schema migration warning: {e}")

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
        from backend.app.services.ebay.auth import eBayOAuth
        
        while True:
            try:
                # Sleep for 60 minutes
                time.sleep(3600)
                
                self.logger.info("Running scheduled token refresh...")
                oauth = eBayOAuth(use_sandbox=False)
                if oauth.refresh_access_token():
                    self.logger.info("Token refreshed successfully (Background)")
                else:
                    self.logger.warning("Background token refresh failed")
                    
            except Exception as e:
                self.logger.error(f"Token maintenance error: {e}")
                time.sleep(300) # Retry sooner on error
    # ... existing methods ...

    def add_folder(self, folder_path: str, metadata: Dict[str, Any] = None) -> QueueJob:
        """Add a single folder to the queue with optional metadata"""
        path = Path(folder_path)
        meta = metadata or {}
        
        job = QueueJob(
            id=uuid.uuid4().hex[:8].upper(),
            folder_path=str(path),
            folder_name=path.name,
            job_metadata=meta,
            scheduled_time=meta.get('scheduled_time') # Extract from metadata if present
        )
        
        session = self.SessionFactory()
        try:
            db_job = self.JobModel(
                id=job.id,
                folder_path=job.folder_path,
                folder_name=job.folder_name,
                status=job.status.value,
                created_at=datetime.fromisoformat(job.created_at),
                job_metadata=job.job_metadata,
                scheduled_time=datetime.fromisoformat(job.scheduled_time) if job.scheduled_time else None,
                
                # Init new fields
                ai_data={},
                item_specifics={},
                timing={}
            )
            session.add(db_job)
            session.commit()
            
            self.emit_event('job_added', job.to_dict())
            return job
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to add job to database: {e}")
            raise
        finally:
            session.close()

    def save_state(self):
        """Syncs all in-memory jobs to the database"""
        # No-op: Since QueueManager is now 100% database-driven, 
        # changes are persisted directly to SQLite and this is no longer needed.
        pass
            
    # ... existing methods ...

    def load_state(self):
        """Load queue state from SQLite database"""
        session = self.SessionFactory()
        try:
            db_jobs = session.query(self.JobModel).all()
            self.jobs = []
            for db_j in db_jobs:
                # Map DB model to QueueJob dataclass
                job = self._db_to_queue_job(db_j)
                
                # Reset any jobs that were processing when we closed
                if job.status == JobStatus.PROCESSING:
                    job.status = JobStatus.PENDING
                    db_j.status = JobStatus.PENDING.value
                
                self.jobs.append(job)
            
            session.commit()
            self.logger.info(f"Loaded {len(self.jobs)} jobs from SQLite database")
            
        except Exception as e:
            self.logger.error(f"Error loading queue state from database: {e}")
            self.jobs = []
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

    def _db_to_queue_job(self, db_j) -> QueueJob:
        return QueueJob(
            id=db_j.id,
            folder_path=db_j.folder_path,
            folder_name=db_j.folder_name,
            status=JobStatus(db_j.status),
            listing_id=db_j.listing_id,
            offer_id=db_j.offer_id,
            price=db_j.price,
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
            job_metadata=db_j.job_metadata or {}
        )

    def _watch_inbox(self):
        """Background thread to watch for new items in inbox"""
        self.logger.info(f"Inbox Watcher started on: {self.inbox_path}")
        
        while True:
            try:
                time.sleep(10) # Check every 10 seconds
                
                if not self.inbox_path.exists():
                    continue
                    
                # Import here to avoid circular dependency
                from backend.app.services.scanner_service import ScannerService
                
                scanner = ScannerService(self.inbox_path)
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

    def set_processor(self, processor: Callable[[str], dict]):
        """Deprecated: Processor is now hardwired to ProcessorService"""
        pass
        
    def _process_queue(self):
        """Background worker to process jobs sequentially"""
        while True:
            try:
                # Check for pause
                if self._paused:
                    time.sleep(0.1)
                    continue
                
                # Get next pending job
                job = self._get_next_pending()
                if not job:
                    # No pending jobs — check if we should exit
                    stats = self.get_stats()
                    if stats['pending'] == 0 and stats['processing'] == 0:
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
        
        self._processing = False
        if self.on_queue_complete:
            self.on_queue_complete()
        
    def add_batch(self, folder_paths: List[str]) -> List[QueueJob]:
        """Add multiple folders to the queue"""
        jobs = []
        for path in folder_paths:
            jobs.append(self.add_folder(path))
        return jobs
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue (only if pending or failed)"""
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(id=job_id).first()
            if db_job and db_job.status in [JobStatus.PENDING.value, JobStatus.FAILED.value, JobStatus.SKIPPED.value]:
                session.delete(db_job)
                session.commit()
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
    
    def clear_completed(self):
        """Remove all completed and skipped jobs from the queue"""
        session = self.SessionFactory()
        try:
            session.query(self.JobModel).filter(
                self.JobModel.status.in_([JobStatus.COMPLETED.value, JobStatus.SKIPPED.value])
            ).delete(synchronize_session=False)
            session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()
            
    def clear_failed(self):
        """Remove all failed jobs from the queue"""
        session = self.SessionFactory()
        try:
            session.query(self.JobModel).filter(
                self.JobModel.status == JobStatus.FAILED.value
            ).delete(synchronize_session=False)
            session.commit()
        except Exception as e:
            session.rollback()
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
        if self._processing:
            return
        
        # Self-contained processing now
        
        self._processing = True
        self._paused = False
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()
    
    def pause(self):
        """Pause processing after current job completes"""
        self._paused = True
    
    def resume(self):
        """Resume processing"""
        if self._paused:
            self._paused = False
            if not self._processing:
                self.start_processing()
    
    def is_processing(self) -> bool:
        """Check if queue is actively processing"""
        return self._processing and not self._paused
    
    def is_paused(self) -> bool:
        """Check if queue is paused"""
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
            if db_job and db_job.status == JobStatus.FAILED.value and db_job.attempts < db_job.max_attempts:
                db_job.status = JobStatus.PENDING.value
                db_job.error_type = None
                db_job.error_message = None
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
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now().isoformat()
        job.attempts += 1
        self.save_state()
        self.emit_event('job_update', job.to_dict())
        self.log_status(job.id, "🚀 Starting processing pipeline...")
        
        if self.on_job_start:
            self.on_job_start(job)
        
        try:
            start_time = time.time()
            self.log_status(job.id, "🔍 Analyzing images with AI...")
            
            # Instantiate ProcessorService (Phase 3 Architecture)
            # The service handles its own dependencies (eBayService, TemplateManager)
            from backend.app.services.processor_service import ProcessorService
            processor = ProcessorService()
            
            # Create callback for logging
            def job_log_callback(msg, level='info'):
                self.log_status(job.id, msg, level)
            
            # Pass job object directly to processor (New Architecture)
            result = processor.create_listing(job, log_callback=job_log_callback)
            
            elapsed = time.time() - start_time
            
            # Handle result
            if isinstance(result, dict):
                if result.get('success', False) or result.get('listing_id') or result.get('offer_id'):
                    job.status = JobStatus.COMPLETED
                    job.listing_id = result.get('listing_id')
                    job.offer_id = result.get('offer_id')
                    job.price = result.get('price')
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
            if type(e).__name__ == 'NeedsReviewException':
                self.log_status(job.id, f"⚠️ Needs Review: {str(e)}", "warning")
                job.status = JobStatus.NEEDS_REVIEW
                job.error_message = str(e)
                job.error_type = "needs_review"
                # Prevent automatic retries for this state
                job.attempts = job.max_attempts
            else:
                job.status = JobStatus.FAILED
                job.error_type = type(e).__name__
                job.error_message = str(e)
        
        job.completed_at = datetime.now().isoformat()
        
        # PERSIST TO DATABASE
        session = self.SessionFactory()
        try:
            db_job = session.query(self.JobModel).filter_by(id=job.id).first()
            if db_job:
                db_job.status = job.status.value
                db_job.listing_id = job.listing_id
                db_job.offer_id = job.offer_id
                db_job.price = job.price
                db_job.error_type = job.error_type
                db_job.error_message = job.error_message
                db_job.attempts = job.attempts
                db_job.started_at = datetime.fromisoformat(job.started_at)
                db_job.completed_at = datetime.fromisoformat(job.completed_at)
                db_job.timing = job.timing
                db_job.job_metadata = job.job_metadata
                
                # Persist Rich Data
                db_job.ai_data = job.ai_data
                db_job.item_specifics = job.item_specifics
                
                session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to persist job result to database: {e}")
        finally:
            session.close()

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
        except Exception:
            pass
        finally:
            session.close()

        return None


# Test the queue manager
if __name__ == "__main__":
    print("Testing Queue Manager...\n")
    
    qm = QueueManager()
    
    # Clear any previous state for clean test
    qm.clear_all()
    
    # Add some test jobs
    test_folders = [
        r"C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\cletop_cleaner",
        r"C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\svbony_scope",
        r"C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\user_test_item"
    ]
    
    for folder in test_folders:
        if Path(folder).exists():
            job = qm.add_folder(folder)
            print(f"Added: {job.folder_name} (ID: {job.id})")
    
    print(f"\nQueue stats: {qm.get_stats()}")
    
    # Test state persistence
    print("\nSaving and reloading state...")
    qm.save_state()
    
    qm2 = QueueManager()
    print(f"Reloaded {len(qm2.jobs)} jobs")
    for job in qm2.jobs:
        print(f"  - {job.folder_name}: {job.status.value}")
    
    print("\n✅ Queue Manager test complete!")