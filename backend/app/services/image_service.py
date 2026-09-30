"""
Backwards-compatibility wrapper for ImageService.
Consolidated under backend.app.services.item_media.ItemMedia.
"""
from backend.app.services.item_media import ItemMedia
from backend.app.core.logger import get_logger

logger = get_logger('image_service')


class ImageService(ItemMedia):
    """Backwards-compatibility service for job image operations.
    Unused dead method save_edits has been retired.
    """
    pass
