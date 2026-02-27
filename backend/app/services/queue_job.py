"""
Queue Job Data Model for eBay Draft Commander.

Contains the job data structures and helpers used across the application.
Separated from queue_manager.py so AI/LLM tools can load just the data model
without pulling in the full orchestration layer (threading, DB, Socket.IO).

Typical usage:
    from backend.app.services.queue_job import QueueJob, JobStatus, resolve_thumbnail
"""
from enum import Enum
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any


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
    """Represents a single listing job in the queue.

    Fields are grouped by concern:
    - Identity: id, folder_path, folder_name
    - Core Data: listing_id, offer_id, price
    - User Overrides: user_title, user_price, user_description, user_condition
    - Rich Data: ai_data, item_specifics (stored as JSON in DB)
    - Error Handling: error_type, error_message, attempts, max_attempts
    - Timing & Meta: created_at, started_at, completed_at, scheduled_time, timing, job_metadata
    - Cached: thumbnail_name (avoids N+1 filesystem scan on /jobs list)
    """
    id: str
    folder_path: str
    folder_name: str
    status: JobStatus = JobStatus.PENDING

    # Core Data
    listing_id: Optional[str] = None
    offer_id: Optional[str] = None
    price: Optional[str] = None
    title: Optional[str] = None
    condition: Optional[str] = None

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

    # Cached thumbnail (avoids N+1 filesystem scan on /jobs list)
    thumbnail_name: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.status == JobStatus.FAILED and self.attempts < self.max_attempts


def resolve_thumbnail(folder_path: str) -> Optional[str]:
    """Resolve the thumbnail filename for a job folder (single filesystem scan).

    Priority: cover.jpg > cover.png > first supported image file.
    Returns just the filename (e.g. 'cover.jpg', 'IMG_001.png'), or None if no images.
    """
    from backend.app.core.constants import SUPPORTED_IMAGE_EXTENSIONS
    folder = Path(folder_path)
    if not folder.exists():
        return None

    # Fast path: check for explicit cover files
    for cover_name in ('cover.jpg', 'cover.jpeg', 'cover.png'):
        if (folder / cover_name).exists():
            return cover_name

    # Single-pass scan for first supported image
    try:
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                return f.name
    except OSError:
        pass

    return None
