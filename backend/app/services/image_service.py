from pathlib import Path
from backend.app.core.logger import get_logger

logger = get_logger('image_service')

try:
    from PIL import Image, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("Pillow not installed. Photo editing disabled.")

try:
    from rembg import remove
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False
    logger.warning("rembg not installed. Auto-background removal disabled.")

class ImageService:
    """Service for handling image operations"""

    def get_job_images(self, job_id, queue_manager):
        """Get list of images for a job"""
        job = queue_manager.get_job_by_id(job_id)
        if not job:
            return None
        
        folder_path = Path(job.folder_path)
        images = []
        
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
            for img_path in sorted(folder_path.glob(ext)):
                images.append({
                    'name': img_path.name,
                    'url': f'/api/job/{job_id}/image/{img_path.name}'
                })
        
        return images

    def get_image_path(self, job_id, filename, queue_manager):
        """Result absolute path to a job image"""
        job = queue_manager.get_job_by_id(job_id)
        if not job:
            return None
            
        folder_path = Path(job.folder_path)
        image_path = folder_path / filename
        
        if not image_path.exists():
            return None
            
        return str(image_path)

    def save_edits(self, job_id, edits, queue_manager):
        """Apply and save edits to an image"""
        if not HAS_PIL:
             return {'success': False, 'error': 'Server missing Pillow library'}, 500

        try:
            job = queue_manager.get_job_by_id(job_id)
            if not job:
                return {'success': False, 'error': 'Job not found'}, 404

            folder_path = Path(job.folder_path)
            # Naive: find first image if specific one not requested? 
            # Original code: image_files = list...; target = sorted(image_files)[0]
            # Ideally we should pass filename, but for now matching original behavior
            image_files = list(folder_path.glob('*.jpg')) + list(folder_path.glob('*.png'))
            if not image_files:
                return {'success': False, 'error': 'No images found in job folder'}, 404
            
            target_image = sorted(image_files)[0]
            
            with Image.open(target_image) as img:
                # 1. Background Removal (Should be first)
                if edits.get('remove_background'):
                    if HAS_REMBG:
                        # Convert to RGBA for transparency
                        img = img.convert("RGBA")
                        img = remove(img)
                        # Fill background with white instead of leaving transparent 
                        # (eBay prefers white backgrounds)
                        new_img = Image.new("RGBA", img.size, "WHITE")
                        new_img.paste(img, (0, 0), img)
                        img = new_img.convert("RGB")
                    else:
                        logger.warning("Background removal requested but rembg not available.")

                # 2. Rotation
                rotation = edits.get('rotation', 0)
                if rotation:
                    img = img.rotate(-rotation, expand=True)
                
                # 3. Crop
                crop = edits.get('crop')
                if crop:
                    w, h = img.size
                    left = crop['x'] * w / 100
                    top = crop['y'] * h / 100
                    img = img.crop((left, top, left + (crop['width'] * w / 100), top + (crop['height'] * h / 100)))

                # 4. Adjustments
                adj = edits.get('adjustments', {})
                if adj:
                    if 'brightness' in adj:
                        img = ImageEnhance.Brightness(img).enhance(adj['brightness'] / 50.0)
                    if 'contrast' in adj:
                        img = ImageEnhance.Contrast(img).enhance(adj['contrast'] / 50.0)
                    if 'saturation' in adj:
                        img = ImageEnhance.Color(img).enhance(adj['saturation'] / 50.0)
                    if 'sharpness' in adj:
                        img = ImageEnhance.Sharpness(img).enhance(adj['sharpness'] / 50.0)
                        
                img.save(target_image, quality=95)
                
            return {'success': True, 'message': 'Image saved successfully'}, 200

        except Exception as e:
            logger.exception(f"Photo save error for job {job_id}")
            return {'success': False, 'error': str(e)}, 500
