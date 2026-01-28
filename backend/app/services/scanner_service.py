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

    def scan_inbox(self, queue_manager: QueueManager) -> Dict[str, Any]:
        """
        Scan inbox folder for new items and add them to the queue.
        Returns statistics about the scan.
        """
        if not self.inbox_path.exists():
            return {'success': False, 'error': 'Inbox directory not found', 'added': 0}

        folders = [f for f in self.inbox_path.iterdir() if f.is_dir()]
        logger.info(f"Scanning inbox: {self.inbox_path}, found {len(folders)} folders")
        
        added_count = 0
        skipped_count = 0
        
        for folder in folders:
            # Check for images (case insensitive extensions)
            images = list(folder.glob('*.jpg')) + list(folder.glob('*.jpeg')) + \
                     list(folder.glob('*.png')) + list(folder.glob('*.JPG'))
            
            if images:
                # Check if already in queue
                # Note: QueueManager.get_job_by_folder might return a job or None
                existing = queue_manager.get_job_by_folder(folder.name)
                
                if not existing:
                    try:
                        queue_manager.add_folder(str(folder))
                        added_count += 1
                        logger.info(f"Added new job from folder: {folder.name}")
                    except Exception as e:
                        logger.error(f"Failed to add folder {folder.name}: {e}")
                else:
                    skipped_count += 1
            else:
                logger.debug(f"Skipping empty/no-image folder: {folder.name}")
                
        return {
            'success': True,
            'added': added_count,
            'skipped': skipped_count,
            'total_scanned': len(folders)
        }
