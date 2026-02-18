import sys
import sqlite3
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load Env
config = {}
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                config[k] = v

USER_TOKEN = config.get('EBAY_USER_TOKEN')
HEADERS = {
    'Authorization': f'Bearer {USER_TOKEN}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

def reset_and_cleanup():
    print("🧹 Starting Cleanup...")
    
    # 1. Fetch offers to delete from DB
    conn = sqlite3.connect(PROJECT_ROOT / 'data' / 'commander.db')
    c = conn.cursor()
    # Get offers that are completed but have NO listing ID (the stuck ones)
    c.execute("SELECT folder_name, offer_id FROM jobs WHERE status='completed' AND listing_id IS NULL")
    rows = c.fetchall()
    
    deleted_count = 0
    
    if rows:
        print(f"🗑️ Deleting {len(rows)} failed offers from eBay...")
        for r in rows:
            name, offer_id = r
            if offer_id:
                # Delete Offer API
                # Note: Inventory API uses 'deleteOffer' but we usually just delete the inventory item or ignore.
                # Actually, best practice to avoid clutter is to delete the offer.
                url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}"
                resp = requests.delete(url, headers=HEADERS)
                if resp.status_code == 204:
                    print(f"   ✅ Deleted Offer {offer_id} ({name})")
                    deleted_count += 1
                else:
                    print(f"   ⚠️ Could not delete {offer_id} ({resp.status_code}) - might be already gone.")
    else:
        print("   No stuck offers found in DB to delete.")
        
    # 2. Clear DB
    print("💥 Clearing Local Database...")
    c.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()
    
    project_root_str = str(PROJECT_ROOT)
    print(f"✅ Database wiped. All inbox items will be treated as NEW.")
    print("----------------------------------------------------------------")
    print("READY TO RE-RUN.")
    print("Run: python tools/process_inbox_now.py")

if __name__ == "__main__":
    reset_and_cleanup()
