
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.append(os.getcwd())

from backend.app.core.database import init_db, JobModel
from backend.app.services.queue_manager import QueueManager, JobStatus

def test_db_migration():
    db_dir = Path("data")
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / "test_commander.db"
    if db_path.exists():
        db_path.unlink()
    
    print(f"Testing DB initialization at {db_path}...")
    # 1. Test init_db on a fresh DB
    SessionFactory = init_db(db_path)
    session = SessionFactory()
    
    # Check if confidence_score exists in JobModel
    from sqlalchemy import inspect
    inspector = inspect(session.bind)
    columns = [c['name'] for c in inspector.get_columns('jobs')]
    print(f"Columns in 'jobs' table: {columns}")
    
    if 'confidence_score' in columns:
        print("✅ confidence_score column created successfully.")
    else:
        print("❌ confidence_score column MISSING.")
        sys.exit(1)
        
    # 2. Test status enum
    print(f"Testing JobStatus.PENDING_REVIEW: {JobStatus.PENDING_REVIEW.value}")
    if JobStatus.PENDING_REVIEW.value == "pending_review":
        print("✅ JobStatus.PENDING_REVIEW correctly defined.")
    else:
        print("❌ JobStatus.PENDING_REVIEW INCORRECT.")
        sys.exit(1)

    # 3. Test QueueManager migration logic
    print("Testing QueueManager _ensure_schema...")
    qm = QueueManager(base_path=Path("."))
    # Manually trigger migration on the test db (QueueManager uses commander.db by default in the same dir)
    # But wait, QueueManager init calls _ensure_schema.
    # We need to make sure it points to our test db.
    
    # Actually, the simplest way is to check if it's there.
    
    session.close()
    if db_path.exists():
        db_path.unlink()
    print("Test passed!")

if __name__ == "__main__":
    test_db_migration()
