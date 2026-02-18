import sqlite3
from pathlib import Path

db_path = Path("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/data/commander.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, folder_name, status, error_message FROM jobs ORDER BY started_at DESC LIMIT 1")
job = cursor.fetchone()

if job:
    with open("last_error.txt", "w", encoding="utf-8") as f:
        f.write(f"Job ID: {job[0]}\n")
        f.write(f"Status: {job[2]}\n")
        f.write(f"Error Message: {job[3]}\n")
    print("Error written to last_error.txt")
else:
    print("No jobs found")

conn.close()
