import sys
import time
from pathlib import Path

# Add project root to path
sys.path.append("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander")

from backend.app.services.queue_manager import QueueManager, JobStatus
from backend.app import create_app

def run_queue():
    print("🚀 Starting Manual Queue Processor...")
    
    # 1. Initialize QueueManager
    qm = QueueManager()
    
    # 2. Initialize App with QM
    app = create_app(queue_manager=qm)
    
    # 3. Add the 'igen made in japan' folder
    # Ideally, scan inbox, but let's be specific or just scan inbox
    inbox_path = Path(r"c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander\inbox")
    target_folder = inbox_path / "igen made in japan"
    
    if target_folder.exists():
        print(f"📥 Found Inbox Item: {target_folder.name}")
        job = qm.add_folder(str(target_folder))
        print(f"   Created Job ID: {job.id}")
        
        # 4. Start Processing
        print("▶️  Starting Processing...")
        qm.start_processing()
        
        # 5. Monitor
        while True:
            updated_job = qm.get_job_by_id(job.id)
            if not updated_job:
                print("❌ Job vanished!")
                break
                
            status = updated_job.status
            print(f"   Status: {status.value}...")
            
            if status in [JobStatus.COMPLETED]:
                print(f"\n✅ SUCCESS!")
                print(f"   Title: {updated_job.listing_id} (Note: check result for actual title if listing_id is confusing)")
                print(f"   Price: ${updated_job.price}")
                print(f"   Offer ID: {updated_job.offer_id}")
                break
                
            if status in [JobStatus.FAILED]:
                print(f"\n❌ FAILED!")
                print(f"   Error: {updated_job.error_message}")
                break
                
            time.sleep(2)
            
    else:
        print(f"⚠️ Target folder not found: {target_folder}")

if __name__ == "__main__":
    run_queue()
