import sys
import os
import shutil
import time
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.queue_manager import QueueManager, JobStatus

def verify_migration():
    print("[START] Starting Database Verification...")
    
    # 1. Initialize QueueManager
    print("   Initializing QueueManager...")
    qm = QueueManager()
    print(f"   DB Path: {qm.db_path}")
    print(f"   Base Path: {qm.base_path}")
    
    initial_count = len(qm.jobs)
    print(f"   [OK] Loaded {initial_count} existing jobs from Database.")
    
    import uuid
    # 2. Create Dummy Job Folder
    inbox_dir = qm.base_path / "inbox"
    folder_name = f"VERIFICATION_TEST_{uuid.uuid4().hex[:8]}"
    test_folder = inbox_dir / folder_name
    
    # Cleanup any old test folders if possible (best effort)
    for p in inbox_dir.glob("VERIFICATION_TEST_*"):
        try:
            shutil.rmtree(p)
        except:
            pass
            
    test_folder.mkdir(parents=True, exist_ok=True)
    
    # Create a dummy image to pass validity checks
    with open(test_folder / "test.jpg", "w") as f:
        f.write("dummy image content")
        
    print(f"   Created test folder: {test_folder}")
    
    # 3. Add to Queue
    print("   Adding job to queue...")
    job = qm.add_folder(str(test_folder))
    print(f"   [OK] Job added with ID: {job.id}")
    
    # 4. Modify Job Data (Test new fields)
    print("   Modifying job fields (user_title, user_price)...")
    job.user_title = "VERIFIED_TITLE_UPDATE"
    job.user_price = "999.99"
    job.ai_data = {"test_key": "test_value"}
    
    # 5. Save State
    print("   Saving state to Database...")
    qm.save_state()
    
    # 6. Reload to Verify Persistence
    print("   Reloading QueueManager to verify persistence...")
    qm2 = QueueManager()
    reloaded_job = qm2.get_job_by_id(job.id)
    
    if not reloaded_job:
        print("   [ERROR] ERROR: Job not found after reload!")
        sys.exit(1)
        
    print(f"   Inspect reloaded job: {reloaded_job.user_title}, {reloaded_job.user_price}")
    
    if reloaded_job.user_title != "VERIFIED_TITLE_UPDATE":
        print(f"   [ERROR] ERROR: user_title mismatch! Got {reloaded_job.user_title}")
        sys.exit(1)
        
    if reloaded_job.ai_data.get('test_key') != "test_value":
        print(f"   [ERROR] ERROR: ai_data mismatch! Got {reloaded_job.ai_data}")
        sys.exit(1)
        
    print("   [OK] Data persistence verified successfully!")
    
    # 7. Cleanup
    print("   Cleaning up...")
    qm2.remove_job(job.id)
    try:
        if test_folder.exists():
            shutil.rmtree(test_folder)
    except Exception as e:
        print(f"   [WARN] Failed to delete test folder: {e}")
    print("   [OK] Cleanup complete.")
    
    print("\n[SUCCESS] MIGRATION VERIFICATION PASSED!")

if __name__ == "__main__":
    verify_migration()
