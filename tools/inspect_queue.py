import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Path to the database
db_path = Path("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/data/commander.db")

print(f"📂 Inspecting Queue Database: {db_path}")

if not db_path.exists():
    print("❌ Database file not found!")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check jobs table
    cursor.execute("SELECT id, folder_name, status, created_at, error_message FROM jobs")
    jobs = cursor.fetchall()
    
    print(f"\n📊 Queue Summary: Found {len(jobs)} total jobs")
    print("-" * 60)
    print(f"{'ID':<10} | {'Status':<10} | {'Folder Name':<30}")
    print("-" * 60)
    
    pending_count = 0
    for job in jobs:
        job_id, folder_name, status, created_at, error = job
        if status in ['pending', 'failed', 'processing']:
            print(f"{job_id:<10} | {status:<10} | {folder_name:<30}")
            if error and status == 'failed':
                 print(f"           ⚠️ Error: {error[:80]}...")
            pending_count += 1
            
    print("-" * 60)
    print(f"📝 Total Active/Pending Items: {pending_count}")
    
    conn.close()

except Exception as e:
    print(f"❌ Error reading database: {e}")
