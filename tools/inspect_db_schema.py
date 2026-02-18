import sqlite3
from pathlib import Path
import json

db_path = Path("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/data/commander.db")

def inspect_reasoning():
    if not db_path.exists():
        print("❌ Database not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Get Columns
    cursor.execute("PRAGMA table_info(jobs)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"📊 Schema Columns: {columns}")
    
    # 2. Check if 'reasoning' or 'result' or 'ai_data' exists
    # If not, we might be out of luck for historical reasoning unless it's in a JSON column
    
    # 3. Fetch last job
    cursor.execute(f"SELECT * FROM jobs ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print("\n📝 Last Job Data:")
        data = dict(zip(columns, row))
        for k, v in data.items():
            if k in ['id', 'folder_name', 'status', 'error_message', 'price']:
                 print(f"   {k}: {v}")
            # If there's a blob/json column, try to parse it
            if k in ['result', 'data', 'meta']:
                 print(f"   {k} (raw): {v}")
    else:
        print("No jobs found.")
        
    conn.close()

if __name__ == "__main__":
    inspect_reasoning()
