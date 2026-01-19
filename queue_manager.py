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
from logger import get_logger


class JobStatus(Enum):
    """Status of a queue job"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"


@dataclass
class QueueJob:
    """Represents a single listing job in the queue"""
    id: str
    folder_path: str
    folder_name: str
    status: JobStatus = JobStatus.PENDING
    listing_id: Optional[str] = None
    offer_id: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    timing: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'QueueJob':
        """Create from dict (for loading from JSON)"""
        data['status'] = JobStatus(data['status'])
        return cls(**data)
    
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
        self.base_path = base_path or Path(__file__).parent
        self.data_path = self.base_path / "data"
        self.data_path.mkdir(exist_ok=True)
        self.state_file = self.data_path / "queue_state.json"
        
        self.jobs: List[QueueJob] = []
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
        
        # Processing function (injected from create_from_folder)
        self._processor: Optional[Callable[[str], dict]] = None
        
        # Initialize logger
        self.logger = get_logger('queue_manager', level='DEBUG')
        
        # Load any persisted state
        self.load_state()
    
    def set_processor(self, processor: Callable[[str], dict]):
        """Set the function that processes a folder into a listing"""
        self._processor = processor
    
    def add_folder(self, folder_path: str) -> QueueJob:
        """Add a single folder to the queue"""
        path = Path(folder_path)
        job = QueueJob(
            id=uuid.uuid4().hex[:8].upper(),
            folder_path=str(path),
            folder_name=path.name
        )
        with self._lock:
            self.jobs.append(job)
        self.save_state()
        return job
    
    def add_batch(self, folder_paths: List[str]) -> List[QueueJob]:
        """Add multiple folders to the queue"""
        jobs = []
        for path in folder_paths:
            jobs.append(self.add_folder(path))
        return jobs
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue (only if pending or failed)"""
        with self._lock:
            for i, job in enumerate(self.jobs):
                if job.id == job_id and job.status in [JobStatus.PENDING, JobStatus.FAILED, JobStatus.SKIPPED]:
                    self.jobs.pop(i)
                    self.save_state()
                    return True
        return False
    
    def skip_job(self, job_id: str) -> bool:
        """Skip a pending job"""
        with self._lock:
            for job in self.jobs:
                if job.id == job_id and job.status == JobStatus.PENDING:
                    job.status = JobStatus.SKIPPED
                    self.save_state()
                    return True
        return False
    
    def clear_completed(self):
        """Remove all completed and skipped jobs from the queue"""
        with self._lock:
            self.jobs = [j for j in self.jobs if j.status not in [JobStatus.COMPLETED, JobStatus.SKIPPED]]
        self.save_state()
    
    def clear_all(self):
        """Clear all jobs from the queue"""
        with self._lock:
            self.jobs = []
        self.save_state()
    
    def get_pending_jobs(self) -> List[QueueJob]:
        """Get all pending jobs"""
        return [j for j in self.jobs if j.status == JobStatus.PENDING]
    
    def get_failed_jobs(self) -> List[QueueJob]:
        """Get all failed jobs"""
        return [j for j in self.jobs if j.status == JobStatus.FAILED]
    
    def get_stats(self) -> dict:
        """Get queue statistics"""
        stats = {
            'total': len(self.jobs),
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0
        }
        for job in self.jobs:
            stats[job.status.value] += 1
        return stats
    
    def start_processing(self):
        """Start processing the queue in background thread"""
        if self._processing:
            return
        
        if not self._processor:
            raise ValueError("No processor function set. Call set_processor() first.")
        
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
    
    def retry_failed(self):
        """Reset all failed jobs to pending for retry"""
        with self._lock:
            for job in self.jobs:
                if job.can_retry():
                    job.status = JobStatus.PENDING
                    job.error_type = None
                    job.error_message = None
        self.save_state()
    
    def retry_job(self, job_id: str) -> bool:
        """Retry a specific failed job"""
        with self._lock:
            for job in self.jobs:
                if job.id == job_id and job.can_retry():
                    job.status = JobStatus.PENDING
                    job.error_type = None
                    job.error_message = None
                    self.save_state()
                    return True
        return False
    
    def _process_queue(self):
        """Background worker to process jobs sequentially"""
        try:
            while True:
                # Check for pause
                if self._paused:
                    time.sleep(0.1)
                    continue
                
                # Get next pending job
                job = self._get_next_pending()
                if not job:
                    break
                
                # Process it
                self._process_job(job)
                
                # Update progress
                stats = self.get_stats()
                done = stats['completed'] + stats['failed'] + stats['skipped']
                if self.on_progress:
                    self.on_progress(done, stats['total'])
        finally:
            self._processing = False
            if self.on_queue_complete:
                self.on_queue_complete()
    
    def _get_next_pending(self) -> Optional[QueueJob]:
        """Get next pending job (thread-safe)"""
        with self._lock:
            for job in self.jobs:
                if job.status == JobStatus.PENDING:
                    return job
        return None
    
    def _process_job(self, job: QueueJob):
        """Process a single job"""
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now().isoformat()
        job.attempts += 1
        self.save_state()
        
        if self.on_job_start:
            self.on_job_start(job)
        
        try:
            start_time = time.time()
            result = self._processor(job.folder_path)
            elapsed = time.time() - start_time
            
            # Handle result
            if isinstance(result, dict):
                if result.get('success', False) or result.get('listing_id') or result.get('offer_id'):
                    job.status = JobStatus.COMPLETED
                    job.listing_id = result.get('listing_id')
                    job.offer_id = result.get('offer_id')
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
            job.status = JobStatus.FAILED
            job.error_type = type(e).__name__
            job.error_message = str(e)
        
        job.completed_at = datetime.now().isoformat()
        self.save_state()
        
        if job.status == JobStatus.COMPLETED:
            if self.on_job_complete:
                self.on_job_complete(job)
        else:
            if self.on_job_error:
                self.on_job_error(job)
    
    def save_state(self):
        """Persist queue state to JSON file"""
        try:
            data = {
                'saved_at': datetime.now().isoformat(),
                'jobs': [job.to_dict() for job in self.jobs]
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save queue state: {e}")
    
    def load_state(self):
        """Load queue state from JSON file"""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            self.jobs = [QueueJob.from_dict(j) for j in data.get('jobs', [])]
            
            # Reset any jobs that were processing when we closed
            for job in self.jobs:
                if job.status == JobStatus.PROCESSING:
                    job.status = JobStatus.PENDING
            
            self.logger.info(f"Loaded {len(self.jobs)} jobs from queue state")
        except json.JSONDecodeError as e:
            self.logger.error(f"Corrupted queue state file", extra={'error': str(e)})
            self.jobs = []
        except Exception as e:
            self.logger.exception("Unexpected error loading queue state")
            self.jobs = []
    
    def get_job_by_id(self, job_id: str) -> Optional[QueueJob]:
        """Get a job by its ID"""
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None
    
    def get_job_by_folder(self, folder_name: str) -> Optional[QueueJob]:
        """Get a job by folder name"""
        for job in self.jobs:
            if job.folder_name == folder_name:
                return job
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
