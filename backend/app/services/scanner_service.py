from pathlib import Path
from typing import List, Dict, Any
from backend.app.services.queue_manager import QueueManager
from backend.app.core.logger import get_logger

logger = get_logger('scanner_service')

class ScannerService:
    def __init__(self, inbox_path: Path):
        self.inbox_path = inbox_path
        if not self.inbox_path.exists():
            try:
                self.inbox_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create inbox directory {self.inbox_path}: {e}")

    CONDITION_FOLDERS = {
        'New', 'New Open Box', 'New With Defects', 'New Old Stock',
        'Like New', 'Used Excellent', 'Used Very Good', 'Used Good',
        'Used Acceptable', 'Certified Refurbished', 'Excellent Refurbished',
        'Very Good Refurbished', 'Good Refurbished', 'For Parts'
    }

    def scan_inbox(self, queue_manager: QueueManager) -> Dict[str, Any]:
        """
        Scan inbox folder for new items and add them to the queue.
        Supports both flat structure and Condition Category subfolders.
        """
        if not self.inbox_path.exists():
            return {'success': False, 'error': 'Inbox directory not found', 'added': 0}

        # Collect all candidate folders
        candidate_folders = []
        
        # 1. Scan root items and detect Condition Folders
        for item in self.inbox_path.iterdir():
            if item.is_dir():
                if item.name in self.CONDITION_FOLDERS:
                    # found a condition category, scan its children (items)
                    subitems = [sub for sub in item.iterdir() if sub.is_dir()]
                    candidate_folders.extend(subitems)
                else:
                    # found a direct item folder (Legacy/Default)
                    candidate_folders.append(item)

        logger.info(f"Scanning inbox: {self.inbox_path}, found {len(candidate_folders)} candidate job folders")
        
        added_count = 0
        skipped_count = 0
        
        for folder in candidate_folders:
            # Check for images (case insensitive extensions)
            images = list(folder.glob('*.jpg')) + list(folder.glob('*.jpeg')) + \
                     list(folder.glob('*.png')) + list(folder.glob('*.JPG'))
            
            if images:
                # Check if already in queue
                # Use folder name for uniqueness. 
                # WARNING: If user names folders same in different categories, this might collision.
                # Ideally queue_manager should use full path, but existing logic uses name.
                # We will trust folder names are unique for now or acceptable collision.
                existing = queue_manager.get_job_by_folder(folder.name)
                
                if not existing:
                    try:
                        # Determine condition from parent folder
                        metadata = {}
                        if folder.parent.name in self.CONDITION_FOLDERS:
                            metadata['condition'] = folder.parent.name
                            
                        queue_manager.add_folder(str(folder), metadata=metadata)
                        added_count += 1
                        logger.info(f"Added new job from folder: {folder.name} (Condition: {metadata.get('condition', 'Default')})")
                    except Exception as e:
                        logger.error(f"Failed to add folder {folder.name}: {e}")
                else:
                    skipped_count += 1
            else:
                pass # logger.debug(f"Skipping empty: {folder.name}")
                
        return {
            'success': True,
            'added': added_count,
            'skipped': skipped_count,
            'total_scanned': len(candidate_folders)
        }
