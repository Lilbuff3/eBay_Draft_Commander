
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(os.getcwd())

from backend.app.services.queue_job import JobStatus, QueueJob
from backend.app.core.database import JobModel

def verify():
    print("1. Verifying JobStatus enum...")
    try:
        status = JobStatus.PENDING_REVIEW
        print(f"✅ JobStatus.PENDING_REVIEW exists: {status.value}")
    except AttributeError:
        print("❌ JobStatus.PENDING_REVIEW MISSING")
        sys.exit(1)

    print("\n2. Verifying QueueJob dataclass...")
    job = QueueJob(id="TEST", folder_path="test", folder_name="test", confidence_score=0.95)
    if hasattr(job, 'confidence_score') and job.confidence_score == 0.95:
        print(f"✅ QueueJob has confidence_score: {job.confidence_score}")
    else:
        print("❌ QueueJob MISSING confidence_score")
        sys.exit(1)

    print("\n3. Verifying JobModel SQLAlchemy column...")
    if hasattr(JobModel, 'confidence_score'):
        print("✅ JobModel has confidence_score column definition")
    else:
        print("❌ JobModel MISSING confidence_score column definition")
        sys.exit(1)

    print("\nVerification successful!")

if __name__ == "__main__":
    verify()
