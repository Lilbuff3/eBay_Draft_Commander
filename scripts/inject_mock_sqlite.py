import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

db_path = Path(__file__).parent / "data" / "commander.db"

def inject_mock():
    # Make sure we can connect to the DB
    if not db_path.exists():
        print(f"DB not found at {db_path}")
        # Search for it elsewhere if needed
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    job_id = uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc).isoformat()
    sched_time = "2026-02-27T07:17:29.000000"

    cursor.execute("""
        INSERT INTO jobs (
            id, folder_path, folder_name, status,
            title, price, condition,
            listing_id,
            user_title, user_price, user_condition,
            ai_json, item_specifics_json, metadata_json,
            source, created_at, scheduled_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id, "C:/MockTest/Coffee_Mug", "Coffee_Mug", "scheduled",
        "White Ceramic Coffee Mug - Good Condition", "9.99", "USED",
        "206081975974",
        "White Ceramic Coffee Mug - Good Condition", "9.99", "USED",
        json.dumps({"listing": {"suggested_title": "White Ceramic Coffee Mug"}}),
        json.dumps({"Brand": ["Unbranded"]}),
        json.dumps({"scheduled_time": "2026-02-27T07:17:29.000Z"}),
        "test_injection", now, sched_time
    ))
    
    conn.commit()
    print(f"Injected Job ID into sqlite: {job_id}")
    conn.close()

if __name__ == "__main__":
    inject_mock()
