import requests
import time
import sys
import json

BASE_URL = "http://127.0.0.1:5000/api"

def log(msg, symbol="ℹ️"):
    print(f"{symbol} {msg}")

def wait_for_server(retries=10):
    for i in range(retries):
        try:
            resp = requests.get(f"{BASE_URL}/status")
            if resp.status_code == 200:
                log("Server is UP", "✅")
                return True
        except:
            pass
        log(f"Waiting for server... ({i+1}/{retries})", "⏳")
        time.sleep(2)
    return False

def run_test():
    if not wait_for_server():
        log("Server failed to start.", "❌")
        sys.exit(1)

    # 1. Scan Inbox
    log("Scanning Inbox...", "🔍")
    try:
        resp = requests.post(f"{BASE_URL}/scan")
        data = resp.json()
        log(f"Scan Result: {json.dumps(data, indent=2)}", "📄")
        
        if not data.get('success'):
            log("Scan failed.", "❌")
            return
            
        if data.get('added', 0) == 0 and data.get('total_scanned', 0) == 0:
             log("No folders found in inbox. Please add 'New Old Stock/MyItem' to test.", "⚠️")
             # Proceeding anyway to check queue status
             
    except Exception as e:
        log(f"Scan Exception: {e}", "❌")
        return

    # 2. Check Queue
    log("Checking Queue...", "📋")
    jobs = []
    try:
        resp = requests.get(f"{BASE_URL}/jobs")
        jobs = resp.json()
        log(f"Found {len(jobs)} jobs in queue.", "🔢")
        
        for job in jobs:
            log(f" - [{job['status']}] {job['name']} (Condition: {job.get('condition', 'None')})", "Job")
            if job.get('condition'):
                 log(f"   Assertion: Condition '{job['condition']}' detected correctly!", "✅")
            else:
                 log(f"   Warning: No condition detected for {job['name']}", "⚠️")

    except Exception as e:
        log(f"Queue Check Failed: {e}", "❌")
        return

    if not jobs:
        log("Queue is empty. Exiting.", "⏹️")
        return

    # 3. Start Processing
    pending = [j for j in jobs if j['status'] == 'pending']
    if pending:
        log(f"Starting Queue ({len(pending)} pending)...", "🚀")
        requests.post(f"{BASE_URL}/start")
        
        # Monitor
        while True:
            time.sleep(2)
            resp = requests.get(f"{BASE_URL}/status")
            status = resp.json()
            # qm status
            state = status.get('status')
            
            # Check individual jobs
            resp_jobs = requests.get(f"{BASE_URL}/jobs")
            current_jobs = resp_jobs.json()
            
            processing = [j for j in current_jobs if j['status'] == 'processing']
            failed = [j for j in current_jobs if j['status'] == 'failed']
            completed = [j for j in current_jobs if j['status'] == 'completed']
            pending = [j for j in current_jobs if j['status'] == 'pending']
            
            log(f"State: {state} | Proc: {len(processing)} | Done: {len(completed)} | Fail: {len(failed)}", "stats")
            
            if len(processing) == 0 and len(pending) == 0:
                log("Queue Processing Finished.", "🏁")
                
                # Report Results
                if failed:
                    log(f"Failures: {len(failed)}", "❌")
                    for f in failed:
                        log(f"  {f['name']}: {f['error_type']}", "  -")
                
                if completed:
                    log(f"Successes: {len(completed)}", "✅")
                    for c in completed:
                         log(f"  {c['name']} -> Price: ${c.get('price')} | Listing: {c.get('listing_id')}", "  -")
                break
    else:
        log("No pending jobs to process.", "INFO")

if __name__ == "__main__":
    run_test()
