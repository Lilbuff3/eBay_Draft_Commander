import time
from pathlib import Path
from PIL import Image
from rembg import remove
from backend.app.services.ebay.media import upload_image_to_eps, check_endpoint_reachability
from backend.app.core.logger import get_logger

logger = get_logger('processor.images')

class ImageProcessor:
    def __init__(self, ebay_service):
        self.ebay_service = ebay_service

    def remove_background_and_square(self, input_path: Path, output_path: Path) -> bool:
        """
        Removes background from an image and composites the subject onto a 2000x2000 white canvas.
        """
        try:
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
            logger.error(f"Failed to process image {input_path.name}: {e}")
            return False

    def upload_images(self, folder_path, ordered_filenames=None, max_images=12, log_callback=None):
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
            images = [p for p in folder_path.glob("*") if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp'] and not p.name.endswith('.orig')]
            
            # Reorder if provided
            if ordered_filenames:
                img_map = {p.name: p for p in images}
                sorted_images = []
                for name in ordered_filenames:
                    if name in img_map:
                        sorted_images.append(img_map.pop(name))
                # Append any remaining that were not in the order list
                sorted_images.extend(sorted(img_map.values(), key=lambda x: x.name))
                images = sorted_images
            else:
                images = sorted(images, key=lambda x: x.name)
                
            images = images[:max_images]

            if not images:
                raise Exception(f"No image files found in {folder_path.name}")

            _log(f"[UPLOAD] Found {len(images)} images to upload. Processing backgrounds first...")

            processed_images = []
            for img_path in images:
                # Skip already processed (or just process if not done)
                if img_path.name.endswith(".orig"):
                    continue
                    
                orig_path = img_path.with_name(f"{img_path.name}.orig")
                
                # Move original out of the way
                import shutil
                shutil.copy2(img_path, orig_path)
                
                _log(f"[IMAGE] Removing background for {img_path.name}...")
                success = self.remove_background_and_square(orig_path, img_path)
                
                if success:
                    processed_images.append(img_path)
                else:
                    _log(f"[IMAGE] Fallback to original for {img_path.name}", level='warning')
                    import os
                    if img_path.exists():
                        os.remove(img_path)
                    shutil.copy2(orig_path, img_path)
                    processed_images.append(img_path)

            # Upload each image, tracking successes and failures
            successful_urls = []
            failed_images = []

            for img in processed_images:
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
