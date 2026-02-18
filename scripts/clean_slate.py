import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.append("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander")

from backend.app.services.queue_manager import QueueManager

def clean_slate():
    print("🧹 Starting Clean Slate Protocol...")
    
    # 1. Clear Database
    qm = QueueManager()
    qm.clear_all()
    print("✅ Database cleared.")
    
    # 2. Clean Inbox
    inbox_path = Path("c:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/inbox")
    
    folders_to_delete = [
        "test_item_01",
        "test_job_1", 
        "mobile_upload_1769165603_a854"
    ]
    
    deleted_count = 0
    
    if inbox_path.exists():
        for folder_name in folders_to_delete:
            target = inbox_path / folder_name
            if target.exists() and target.is_dir():
                try:
                    shutil.rmtree(target)
                    print(f"✅ Deleted: {folder_name}")
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ Failed to delete {folder_name}: {e}")
            else:
                 print(f"ℹ️  Not found (already gone): {folder_name}")
                 
    print(f"\n✨ Cleanup Complete. Removed {deleted_count} demo folders.")
    
    # Verify what's left
    print("\n📦 Remaining Items in Inbox:")
    for item in inbox_path.iterdir():
        if item.is_dir():
            print(f"   - {item.name}")

if __name__ == "__main__":
    clean_slate()
