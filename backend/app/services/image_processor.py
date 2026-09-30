"""
Backwards-compatibility wrapper for ImageProcessor.
Core functionality is consolidated in backend.app.services.item_media.ItemMedia.
"""
from typing import Optional
from backend.app.services.item_media import ItemMedia
from backend.app.services.ebay.media import upload_image_to_eps, check_endpoint_reachability
from backend.app.core.logger import get_logger

logger = get_logger('processor.images')


class ImageProcessor(ItemMedia):
    """ImageProcessor wrapper preserving existing interface and module-level mock points."""

    def __init__(self, ebay_service=None):
        super().__init__(ebay_service=ebay_service)

    @property
    def logger(self):
        return globals().get('logger', logger)

    def upload_images(self, folder_path, ordered_filenames=None, max_images=12, log_callback=None):
        return super().upload_images(
            folder_path,
            ordered_filenames=ordered_filenames,
            max_images=max_images,
            log_callback=log_callback,
            uploader=globals().get('upload_image_to_eps'),
            reachability_checker=globals().get('check_endpoint_reachability'),
        )
