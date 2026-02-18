"""
Migration Script: File System -> SQLite
For eBay Draft Commander

Usage:
    python scripts/migrate_to_sqlite.py
"""
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.app.core.database import init_db, JobModel
from backend.app.core.paths import get_data_dir

def migrate():
    print("🚀 Starting Migration to SQLite...")
    
    # 1. Setup DB
    data_dir = get_data_dir()
    db_path = data_dir / "commander.db"
    print(f"📂 Database Path: {db_path}")
    
    Session = None
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.parent / f"commander.db.bak_{timestamp}"
        try:
            db_path.rename(backup_path)
            print(f"📦 Backed up existing DB to: {backup_path.name}")
        except Exception as e:
            print(f"⚠️ Failed to rename DB (might be locked): {e}")
            print("   Attempting to leverage existing DB (risk of schema mismatch)...")

    Session = init_db(db_path)
    session = Session()
    
    # 2. Find Inbox
    inbox_dir = data_dir.parent / "inbox"
    if not inbox_dir.exists():
        print(f"⚠️ Inbox directory not found at {inbox_dir}")
        return
        
    print(f"📂 Scanning Inbox: {inbox_dir}")
    
    folders = [f for f in inbox_dir.iterdir() if f.is_dir()]
    print(f"Found {len(folders)} folders.")
    
    migrated_count = 0
    skipped_count = 0
    
    for folder in folders:
        try:
            # Check if job already exists in DB (by folder path)
            existing = session.query(JobModel).filter_by(folder_path=str(folder)).first()
            if existing:
                print(f"  [SKIP] {folder.name} (Already in DB)")
                skipped_count += 1
                continue
                
            # Load Data
            job_json_path = folder / "job.json"
            ai_data_path = folder / "ai_data.json"
            
            user_data = {}
            if job_json_path.exists():
                try:
                    with open(job_json_path, 'r', encoding='utf-8') as f:
                        user_data = json.load(f)
                except Exception as e:
                    print(f"    ⚠️ Error reading job.json: {e}")

            ai_data = {}
            if ai_data_path.exists():
                try:
                    with open(ai_data_path, 'r', encoding='utf-8') as f:
                        ai_data = json.load(f)
                except Exception as e:
                    print(f"    ⚠️ Error reading ai_data.json: {e}")
            
            # Determine Status
            status = 'pending'
            if user_data.get('status'): status = user_data['status']
            # Heuristic: if ai_data exists but no listing_id -> processed/pending?
            # Let's default to 'pending' unless we find success markers
            
            # Create JobModel
            job_id = user_data.get('id') or uuid.uuid4().hex[:8].upper()
            
            created_at = datetime.utcnow()
            if user_data.get('created_at'):
                try:
                    # Handle timestamp vs ISO string
                    ts = user_data['created_at']
                    if isinstance(ts, (int, float)):
                        created_at = datetime.fromtimestamp(ts)
                    else:
                        created_at = datetime.fromisoformat(str(ts))
                except: pass

            listing_id = user_data.get('listing_id') or ai_data.get('listing_id')
            
            db_job = JobModel(
                id=job_id,
                folder_path=str(folder),
                folder_name=folder.name,
                status=status,
                created_at=created_at,
                
                # User Overrides
                user_title=user_data.get('user_title'),
                user_price=user_data.get('user_price'),
                user_description=user_data.get('user_description'),
                user_condition=user_data.get('condition'),
                
                # IDs
                listing_id=listing_id,
                offer_id=user_data.get('offer_id'),
                
                # Full Objects
                ai_data=ai_data,
                job_metadata=user_data, # store all user_data as generic metadata too
                
                # Item Specifics (Merge Source)
                item_specifics=ai_data.get('item_specifics') or user_data.get('item_specifics') or {}
            )
            
            # Populate AI suggested Price/Title to main columns if not overridden
            if not db_job.user_title and ai_data.get('listing', {}).get('suggested_title'):
                 # We don't set 'title' directly, we let the logic resolve it at runtime?
                 # Actually, for DB-first, `title` column should probably hold the "Current Active Title"
                 # For now, let's leave `title` empty unless it's a finished listing.
                 pass

            session.add(db_job)
            migrated_count += 1
            print(f"  [OK] {folder.name}")
            
        except Exception as e:
            print(f"  ❌ Failed to migrate {folder.name}: {e}")
            
    try:
        session.commit()
        print(f"\n✅ Migration Complete!")
        print(f"   Migrated: {migrated_count}")
        print(f"   Skipped:  {skipped_count}")
        print(f"   Total DB: {session.query(JobModel).count()}")
    except Exception as e:
        print(f"\n❌ Database Commit Failed: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
