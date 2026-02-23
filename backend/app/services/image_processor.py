import time
from backend.app.services.ebay.media import upload_folder
from backend.app.core.logger import get_logger

logger = get_logger('processor.images')

class ImageProcessor:
    def __init__(self, ebay_service):
        self.ebay_service = ebay_service

    def upload_images(self, folder_path, max_images=12, log_callback=None):
        """Upload images to eBay Picture Services"""
        def _log(msg, level="info"):
            if log_callback: log_callback(msg, level)
            getattr(logger, level)(msg)

        upload_start = time.time()
        try:
            _log(f"☁️ Uploading images to eBay from {folder_path.name}...")
            image_urls = upload_folder(folder_path, max_images=max_images)
            if not image_urls:
                raise Exception("No images were uploaded successfully")
            return {"urls": image_urls, "timing": time.time() - upload_start}
        except Exception as e:
            _log(f"Image upload failed: {e}", level='error')
            return {"error": str(e), "timing": time.time() - upload_start}
