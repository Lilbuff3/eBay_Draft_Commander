"""
Book cover fetching for metadata-created (ISBN) jobs.

Order: Open Library covers API first (~800px, good enough for eBay), then the
caller-provided thumbnail (typically a ~128px Google Books image). eBay
requires >=500px on the longest side, so undersized covers are upscaled.
"""
import io
from pathlib import Path
from typing import Optional

import requests

from backend.app.core.logger import get_logger

logger = get_logger('cover_service')

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("Pillow not installed. Book cover fetching disabled.")

# default=false -> 404 for missing covers instead of a 1x1 transparent gif
OPEN_LIBRARY_URL = 'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false'
MAX_BYTES = 10 * 1024 * 1024
MIN_PLAUSIBLE_PX = 50   # reject tracking-pixel-sized responses
EBAY_MIN_PX = 500       # eBay minimum longest side
UPSCALE_TARGET_PX = 800


def _download(url: str, allow_redirects: bool) -> Optional[bytes]:
    resp = requests.get(url, timeout=10, allow_redirects=allow_redirects)
    if resp.status_code != 200:
        return None
    if len(resp.content) > MAX_BYTES:
        return None
    return resp.content


def fetch_book_cover(isbn: Optional[str], fallback_url: Optional[str], dest_dir: Path) -> Optional[Path]:
    """Download the best available cover into dest_dir/cover.jpg.

    fallback_url must already be SSRF-validated by the caller. The Open
    Library URL is constructed from a validated ISBN, so following its
    redirect (to archive.org) is safe.
    Returns the saved path, or None if no usable cover was found.
    """
    if not HAS_PIL:
        return None

    candidates = []
    if isbn:
        candidates.append((OPEN_LIBRARY_URL.format(isbn=isbn), True))
    if fallback_url:
        candidates.append((fallback_url, False))

    for url, allow_redirects in candidates:
        try:
            raw = _download(url, allow_redirects)
            if not raw:
                continue
            img = Image.open(io.BytesIO(raw))
            img.load()
            if max(img.size) < MIN_PLAUSIBLE_PX:
                continue
            if img.mode != 'RGB':
                img = img.convert('RGB')
            if max(img.size) < EBAY_MIN_PX:
                scale = UPSCALE_TARGET_PX / max(img.size)
                img = img.resize(
                    (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                    Image.LANCZOS,
                )
            dest = dest_dir / 'cover.jpg'
            img.save(dest, 'JPEG', quality=90)
            logger.info(f"Saved cover {img.size} from {url.split('?')[0]}")
            return dest
        except Exception as e:
            logger.warning(f"Cover fetch failed from {url}: {e}")

    return None
