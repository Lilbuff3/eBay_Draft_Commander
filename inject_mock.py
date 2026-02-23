import sys
import os
from pathlib import Path
from datetime import datetime, timezone

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from backend.app.core.database import SessionLocal, JobModel

def inject_mock():
    db = SessionLocal()
    job = JobModel(
        folder_path="C:/MockTest/Coffee_Mug",
        status="scheduled",
        category_id="170599",
        user_title="White Ceramic Coffee Mug - Good Condition",
        user_price="9.99",
        user_condition="USED",
        ai_data={"listing": {"suggested_title": "White Ceramic Coffee Mug"}},
        item_specifics={"Brand": ["Unbranded"]},
        job_metadata={"scheduled_time": "2026-02-27T07:17:29.000Z"},
        listing_id="206081975974",
        scheduled_time="2026-02-27T07:17:29.000Z",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    print(f"Injected Job ID: {job.id}")
    db.close()

if __name__ == "__main__":
    inject_mock()
