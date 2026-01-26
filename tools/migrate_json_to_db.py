"""
Migration Utility: JSON to SQLite
Ports existing queue_state.json and templates folders into commander.db
"""
import sys
import json
import os
from pathlib import Path
from datetime import datetime

# Setup pathing
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.database import init_db, JobModel, TemplateModel

def migrate():
    data_dir = project_root / "data"
    db_path = data_dir / "commander.db"
    
    print(f"🚀 Starting migration to {db_path}...")
    SessionFactory = init_db(db_path)
    session = SessionFactory()
    
    try:
        # 1. Migrate Queue Jobs
        queue_file = data_dir / "queue_state.json"
        if queue_file.exists():
            print("📦 Migrating Queue Jobs...")
            with open(queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                jobs = data.get('jobs', [])
                for j in jobs:
                    # Check if exists
                    if session.query(JobModel).filter_by(id=j['id']).first():
                        continue
                        
                    db_j = JobModel(
                        id=j['id'],
                        folder_path=j['folder_path'],
                        folder_name=j['folder_name'],
                        status=j['status'],
                        listing_id=j.get('listing_id'),
                        offer_id=j.get('offer_id'),
                        price=j.get('price'),
                        error_type=j.get('error_type'),
                        error_message=j.get('error_message'),
                        attempts=j.get('attempts', 0),
                        created_at=datetime.fromisoformat(j['created_at'])
                    )
                    session.add(db_j)
            print(f"✅ Migrated {len(jobs)} jobs")
        
        # 2. Migrate Templates
        template_dir = project_root / "backend" / "app" / "services" / "data" / "templates"
        if template_dir.exists():
            print("📑 Migrating Templates...")
            count = 0
            for t_file in template_dir.glob("*.json"):
                with open(t_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    name = data.get('_name', t_file.stem)
                    
                    if session.query(TemplateModel).filter_by(name=name).first():
                        continue
                        
                    db_t = TemplateModel(name=name)
                    # Strip metadata from data blob
                    db_t.data = {k: v for k, v in data.items() if not k.startswith('_')}
                    db_t.use_count = data.get('_use_count', 0)
                    db_t.created_at = datetime.fromisoformat(data.get('_created_at', datetime.utcnow().isoformat()))
                    session.add(db_t)
                    count += 1
            print(f"✅ Migrated {count} templates")

        session.commit()
        print("\n🎉 Migration Successful!")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Migration Failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
