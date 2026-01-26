"""
Inbox Processor (Trigger Layer)
Scans 'inbox/' and processes folders into eBay Drafts.
"""
import sys
import os
import time
from pathlib import Path

# Add project root
root_path = Path(__file__).parent.parent
sys.path.insert(0, str(root_path))

from backend.app import create_app
from backend.app.services.queue_manager import QueueManager
from backend.app.services.ebay.policies import get_all_policies

def main():
    print("--- B.L.A.S.T. Navigation Trigger: Inbox Processor ---")
    
    # 1. Initialize Flask App (for Config/Context)
    app = create_app()
    
    with app.app_context():
        print("[1/5] Initializing App Context...")
        
        # 2. Pre-load Policies if missing from config
        # (Real app would have a settings page, we'll try to fetch defaults)
        if not app.config.get('EBAY_FULFILLMENT_POLICY'):
            print("  - Fetching default policies...")
            policies = get_all_policies()
            # Simple logic: pick first available
            if policies['fulfillment']: app.config['EBAY_FULFILLMENT_POLICY'] = policies['fulfillment'][0]['id']
            if policies['payment']: app.config['EBAY_PAYMENT_POLICY'] = policies['payment'][0]['id']
            if policies['return']: app.config['EBAY_RETURN_POLICY'] = policies['return'][0]['id']
            if policies['locations']: app.config['EBAY_MERCHANT_LOCATION'] = policies['locations'][0]['id']
            else: app.config['EBAY_MERCHANT_LOCATION'] = 'default'
            
            print(f"  - Using Shipping: {app.config.get('EBAY_FULFILLMENT_POLICY')}")
        
        # 3. Setup Queue
        print("[2/5] Setting up QueueManager...")
        qm = QueueManager()
        qm.set_app(app)
        
        # 4. Scan Inbox
        print("[3/5] Scanning Inbox...")
        inbox_path = root_path / "inbox"
        inbox_path.mkdir(exist_ok=True)
        
        folders = [f for f in inbox_path.iterdir() if f.is_dir()]
        if not folders:
            print("[STOP] Inbox is empty.")
            return

        print(f"  - Found {len(folders)} folders.")
        
        new_jobs = []
        for f in folders:
            # Check if already processed (simple check by name, usually DB check better)
            existing = qm.get_job_by_folder(f.name)
            if not existing:
                job = qm.add_folder(str(f))
                new_jobs.append(job)
                print(f"  + Added: {f.name}")
            else:
                print(f"  . Skipped (Exists): {f.name}")
                
        if not new_jobs:
            print("[STOP] No new jobs to process.")
            # But maybe we have pending jobs?
            if not qm.get_pending_jobs():
                print("       And no pending jobs.")
                return

        # 5. Start Processing
        print("[4/5] Starting Processor...")
        qm.start_processing()
        
        # Monitor Loop
        print("[5/5] Monitoring... (Ctrl+C to stop)")
        try:
            while True:
                stats = qm.get_stats()
                pending = stats['pending'] + stats['processing']
                print(f"\r   Status: {stats}", end="")
                
                if pending == 0:
                    print("\n\n[DONE] All jobs processed.")
                    break
                time.sleep(1)
                
            # Show Results
            print("\nResults:")
            for j in new_jobs:
                updated_job = qm.get_job_by_id(j.id)
                status_icon = "✅" if updated_job.status.value == 'completed' else "❌"
                print(f"  {status_icon} {updated_job.folder_name}: {updated_job.status.value}")
                if updated_job.error_message:
                    print(f"     Error: {updated_job.error_message}")
                if updated_job.offer_id:
                     print(f"     Draft ID: {updated_job.offer_id}")
                     
        except KeyboardInterrupt:
            print("\n[STOP] User interrupted.")

if __name__ == "__main__":
    main()
