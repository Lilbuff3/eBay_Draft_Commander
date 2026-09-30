"""
Unified ItemMedia Service for eBay Draft Commander.
Consolidates job image discovery, safe serving/path traversal guards,
background removal/canvas squaring, and parallel eBay Picture Services (EPS) upload.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from backend.app.core.logger import get_logger
from backend.app.core.validator import validate_safe_path, ValidationError
from backend.app.services.ebay.media import upload_image_to_eps, check_endpoint_reachability

logger = get_logger('item_media')

SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


class ItemMedia:
    """Consolidated media service managing local image inspection, serving,
    processing (rembg), and remote upload (EPS).
    """

    def __init__(self, ebay_service=None, custom_logger=None):
        # Retained for backwards compatibility if callers pass ebay_service
        self.ebay_service = ebay_service
        self._logger = custom_logger

    @property
    def logger(self):
        return self._logger or logger

    def get_job_images(self, job_or_id: Union[str, Any], queue_manager=None) -> Optional[List[Dict[str, str]]]:
        """Get list of images for a job.
        Accepts either (job_id, queue_manager) or a job object / folder_path directly.
        """
        if queue_manager is not None:
            job = queue_manager.get_job_by_id(job_or_id)
            if not job:
                return None
            folder_path = Path(job.folder_path)
            job_id = job_or_id
        elif hasattr(job_or_id, 'folder_path'):
            folder_path = Path(job_or_id.folder_path)
            job_id = getattr(job_or_id, 'id', '')
        else:
            folder_path = Path(job_or_id)
            job_id = folder_path.name

        if not folder_path.exists():
            return None

        images = []
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            for img_path in sorted(folder_path.glob(f"*{ext}")):
                images.append({
                    'name': img_path.name,
                    'url': f'/api/job/{job_id}/image/{img_path.name}'
                })
        return images

    def get_image_path(self, job_or_id: Union[str, Any], filename: str, queue_manager=None) -> Optional[str]:
        """Resolve safe absolute path to a job image, protecting against path traversal."""
        if queue_manager is not None:
            job = queue_manager.get_job_by_id(job_or_id)
            if not job:
                return None
            folder_path = Path(job.folder_path)
            job_id = job_or_id
        elif hasattr(job_or_id, 'folder_path'):
            folder_path = Path(job_or_id.folder_path)
            job_id = getattr(job_or_id, 'id', '')
        else:
            folder_path = Path(job_or_id)
            job_id = folder_path.name

        # Filenames come straight from the URL — reject separators/.. and
        # verify the resolved path stays inside the job folder.
        if not filename or any(s in filename for s in ('/', '\\', '..')):
            logger.warning(f"Rejected suspicious image filename for job {job_id}: {filename!r}")
            return None

        try:
            image_path = validate_safe_path(str(folder_path / filename), base_dir=str(folder_path))
        except ValidationError:
            logger.warning(f"Blocked path traversal attempt for job {job_id}: {filename!r}")
            return None

        if not image_path.exists():
            return None

        return str(image_path)

    def remove_background_and_square(self, input_path: Path, output_path: Path) -> bool:
        """Removes background from an image and composites the subject onto a 2000x2000 white canvas.
        Lazy-imports rembg and PIL to avoid 170MB model download on startup.
        """
        try:
            from PIL import Image
            from rembg import remove
            img = Image.open(input_path)
            output_png = remove(img)

            canvas = Image.new('RGB', (2000, 2000), (255, 255, 255))
            bbox = output_png.getbbox()
            if not bbox:
                return False

            cropped = output_png.crop(bbox)

            # Scale to fit 2000x2000 with margin (target 1900)
            target_size = 1900
            aspect_ratio = cropped.width / cropped.height
            if aspect_ratio > 1:
                new_width = target_size
                new_height = int(target_size / aspect_ratio)
            else:
                new_height = target_size
                new_width = int(target_size * aspect_ratio)

            resized = cropped.resize((new_width, new_height), Image.Resampling.LANCZOS)

            paste_x = (2000 - new_width) // 2
            paste_y = (2000 - new_height) // 2

            mask = resized if resized.mode == 'RGBA' else None
            canvas.paste(resized, (paste_x, paste_y), mask)

            canvas.save(output_path, 'JPEG', quality=90)
            return True
        except Exception as e:
            self.logger.error(f"Failed to process image {input_path.name}: {e}")
            return False

    def upload_images(
        self,
        folder_path,
        ordered_filenames=None,
        max_images=12,
        log_callback=None,
        uploader=None,
        reachability_checker=None,
    ) -> Dict[str, Any]:
        """Upload images to eBay Picture Services with per-image failure tracking."""
        def _log(msg, level="info"):
            if log_callback:
                log_callback(msg, level)
            getattr(logger, level)(msg)

        upload_start = time.time()
        try:
            folder_path = Path(folder_path).resolve()

            # Path traversal guard: ensure folder is within allowed directories
            allowed_dirs = []
            inbox_dir = os.getenv('INBOX_DIR', 'inbox')
            if inbox_dir:
                allowed_dirs.append(Path(inbox_dir).resolve())
            fixtures_dir = Path(__file__).parent.parent.parent.parent / 'tests' / 'fixtures' / 'images'
            if fixtures_dir.exists():
                allowed_dirs.append(fixtures_dir.resolve())

            captures_env = os.getenv('CAPTURES_DIR')
            if captures_env:
                allowed_dirs.append(Path(captures_env).resolve())
            elif inbox_dir:
                allowed_dirs.append((Path(inbox_dir).resolve().parent / 'captures').resolve())

            if allowed_dirs and not any(folder_path == d or folder_path.is_relative_to(d) for d in allowed_dirs):
                raise ValueError(f"Image folder outside allowed directories: {folder_path}")

            _log(f"[UPLOAD] Uploading images to eBay from {folder_path.name}...")

            if not folder_path.exists():
                raise Exception(f"Image folder not found: {folder_path}")

            _reach_fn = reachability_checker or check_endpoint_reachability
            if not _reach_fn():
                raise Exception("eBay image upload endpoint is unreachable - cannot upload images")

            # Gather image files
            images = [
                p for p in folder_path.glob("*")
                if p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS and not p.name.endswith('.orig')
            ]

            # Reorder if provided
            if ordered_filenames:
                img_map = {p.name: p for p in images}
                sorted_images = []
                for name in ordered_filenames:
                    if name in img_map:
                        sorted_images.append(img_map.pop(name))
                sorted_images.extend(sorted(img_map.values(), key=lambda x: x.name))
                images = sorted_images
            else:
                images = sorted(images, key=lambda x: x.name)

            images = images[:max_images]
            if not images:
                raise Exception(f"No image files found in {folder_path.name}")

            bg_removal_enabled = os.getenv('ENABLE_BACKGROUND_REMOVAL', 'false').lower() == 'true'
            if bg_removal_enabled:
                _log(f"[UPLOAD] Found {len(images)} images to upload. Processing backgrounds first...")
                processed_images = []
                import shutil
                for img_path in images:
                    if img_path.name.endswith(".orig"):
                        continue
                    orig_path = img_path.with_name(f"{img_path.name}.orig")
                    shutil.copy2(img_path, orig_path)
                    _log(f"[IMAGE] Removing background for {img_path.name}...")
                    success = self.remove_background_and_square(orig_path, img_path)
                    if success:
                        processed_images.append(img_path)
                    else:
                        _log(f"[IMAGE] Fallback to original for {img_path.name}", level='warning')
                        if img_path.exists():
                            os.remove(img_path)
                        shutil.copy2(orig_path, img_path)
                        processed_images.append(img_path)
            else:
                _log(f"[UPLOAD] Found {len(images)} images to upload")
                processed_images = images

            _upload_fn = uploader or upload_image_to_eps

            def _throttled_upload(img):
                from backend.app.core.rate_limiter import limiter
                limiter.wait_if_needed('ebay')
                return _upload_fn(img)

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(_throttled_upload, img): img for img in processed_images}
                result_map = {}
                for future in as_completed(futures):
                    img = futures[future]
                    try:
                        url = future.result()
                        result_map[img] = url
                    except Exception:
                        logger.warning(f"Upload exception for {img.name}", exc_info=True)

            successful_urls = []
            failed_images = []
            for img in processed_images:
                url = result_map.get(img)
                if url:
                    successful_urls.append(url)
                    _log(f"Uploaded: {img.name} -> {url[:50]}...")
                else:
                    failed_images.append(img.name)
                    _log(f"Failed to upload: {img.name}", level='warning')

            if not successful_urls:
                failed_list = ", ".join(failed_images)
                raise Exception(
                    f"All {len(images)} image uploads failed - cannot create listing without images. "
                    f"Failed files: {failed_list}"
                )

            if failed_images:
                failed_list = ", ".join(failed_images)
                _log(
                    f"[UPLOAD] Partial failure: {len(successful_urls)}/{len(images)} images uploaded. "
                    f"Failed: {failed_list}",
                    level='warning'
                )
            else:
                _log(f"[UPLOAD] All {len(successful_urls)} images uploaded successfully")

            return {
                "urls": successful_urls,
                "timing": time.time() - upload_start,
                "failed_images": failed_images,
                "total_attempted": len(processed_images),
            }

        except Exception as e:
            _log(f"Image upload failed: {e}", level='error')
            return {"error": str(e), "timing": time.time() - upload_start}
