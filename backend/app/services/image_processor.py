import time
from pathlib import Path
from backend.app.services.ebay.media import upload_image_to_eps, check_endpoint_reachability
from backend.app.core.logger import get_logger

logger = get_logger('processor.images')

class ImageProcessor:
    def __init__(self, ebay_service):
        self.ebay_service = ebay_service

    def upload_images(self, folder_path, max_images=12, log_callback=None):
        """Upload images to eBay Picture Services with per-image failure tracking"""
        def _log(msg, level="info"):
            if log_callback: log_callback(msg, level)
            getattr(logger, level)(msg)

        upload_start = time.time()
        try:
            folder_path = Path(folder_path)
            _log(f"[UPLOAD] Uploading images to eBay from {folder_path.name}...")

            if not folder_path.exists():
                raise Exception(f"Image folder not found: {folder_path}")

            # Check endpoint reachability before attempting uploads
            if not check_endpoint_reachability():
                raise Exception("eBay image upload endpoint is unreachable - cannot upload images")

            # Gather image files
            images = [p for p in folder_path.glob("*") if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']]
            images = images[:max_images]

            if not images:
                raise Exception(f"No image files found in {folder_path.name}")

            _log(f"[UPLOAD] Found {len(images)} images to upload")

            # Upload each image, tracking successes and failures
            successful_urls = []
            failed_images = []

            for img in images:
                url = upload_image_to_eps(img)
                if url:
                    successful_urls.append(url)
                else:
                    failed_images.append(img.name)

            # Report results
            total = len(images)
            succeeded = len(successful_urls)
            failed = len(failed_images)

            if succeeded == 0:
                failed_list = ", ".join(failed_images)
                raise Exception(
                    f"All {total} image uploads failed - cannot create listing without images. "
                    f"Failed files: {failed_list}"
                )

            if failed > 0:
                failed_list = ", ".join(failed_images)
                _log(
                    f"[UPLOAD] Partial failure: {succeeded}/{total} images uploaded. "
                    f"Failed: {failed_list}",
                    level='warning'
                )
            else:
                _log(f"[UPLOAD] All {succeeded} images uploaded successfully")

            return {"urls": successful_urls, "timing": time.time() - upload_start}
        except Exception as e:
            _log(f"Image upload failed: {e}", level='error')
            return {"error": str(e), "timing": time.time() - upload_start}
