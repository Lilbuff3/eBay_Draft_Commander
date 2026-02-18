import sys
import requests
import sqlite3
import json
from pathlib import Path

# Add root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

def load_env():
    env_path = PROJECT_ROOT / ".env"
    creds = {}
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    creds[k] = v
    return creds

config = load_env()
USER_TOKEN = config.get('EBAY_USER_TOKEN')
HEADERS = {
    'Authorization': f'Bearer {USER_TOKEN}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

def publish_remaining():
    print(">>> Starting Batch Publish for Stuck Drafts...")
    
    # 1. Get Stuck Jobs from DB
    conn = sqlite3.connect(PROJECT_ROOT / 'data' / 'commander.db')
    c = conn.cursor()
    # "completed" but no "listing_id" means it was created as Offer (draft) but not published
    c.execute("SELECT folder_name, offer_id, listing_id FROM jobs WHERE status='completed' AND listing_id IS NULL")
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        print("[INFO] No stuck drafts found! All completed jobs have listing IDs.")
        return

    print(f"[INFO] Found {len(rows)} unpublished offers. Attempting to publish now...\n")
    
    success_count = 0
    fail_count = 0
    
    for r in rows:
        folder_name = r[0]
        offer_id = r[1]
        
        if not offer_id:
            print(f"[WARN] Skipping {folder_name}: No Offer ID found.")
            continue
            
        print(f"[PUBLISH] Publishing: {folder_name} (Offer: {offer_id})")
        
        try:
            url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish"
            resp = requests.post(url, headers=HEADERS)
            
            if resp.status_code == 200:
                data = resp.json()
                listing_id = data.get('listingId')
                print(f"   [SUCCESS] Listing ID: {listing_id}")
                print(f"   [LINK] https://www.ebay.com/itm/{listing_id}")
                
                # Update DB
                update_db(offer_id, listing_id)
                success_count += 1
            else:
                print(f"   [FAILED] ({resp.status_code})")
                try:
                    errs = resp.json().get('errors', [])
                    for e in errs:
                        print(f"      - {e.get('message')}")
                        if 'domain' in e:
                             print(f"        (Domain: {e.get('domain')}, ID: {e.get('errorId')})")
                except:
                    print(f"      {resp.text}")
                fail_count += 1
                
        except Exception as e:
            print(f"   [EXCEPTION] {e}")
            fail_count += 1
            
        print("-" * 50)

    print(f"\n[SUMMARY] {success_count} Published, {fail_count} Failed")

def update_db(offer_id, listing_id):
    try:
        conn = sqlite3.connect(PROJECT_ROOT / 'data' / 'commander.db')
        c = conn.cursor()
        c.execute("UPDATE jobs SET listing_id = ? WHERE offer_id = ?", (listing_id, offer_id))
        conn.commit()
        conn.close()
    except:
        pass

if __name__ == "__main__":
    publish_remaining()
