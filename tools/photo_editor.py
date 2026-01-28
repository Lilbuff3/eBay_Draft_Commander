"""
Photo Editor for eBay Draft Commander Pro
PIL-based image editing operations
"""
import io
from pathlib import Path
from typing import Optional, Tuple, List
from PIL import Image, ImageEnhance, ImageOps, ImageFilter


class PhotoEditor:
    """Image editing operations for listing photos"""
    
    # Standard eBay image sizes
    EBAY_MAX_SIZE = (1600, 1600)
    EBAY_MIN_SIZE = (500, 500)
    THUMBNAIL_SIZE = (200, 200)
    
    def __init__(self, image_path: Optional[str] = None):
        """
        Initialize photo editor
        
        Args:
            image_path: Optional path to load image from
        """
        self.original: Optional[Image.Image] = None
        self.current: Optional[Image.Image] = None
        self.history: List[Image.Image] = []
        self.path: Optional[Path] = None
        
        if image_path:
            self.load(image_path)
    
    def load(self, image_path: str) -> 'PhotoEditor':
        """Load an image from file"""
        self.path = Path(image_path)
        self.original = Image.open(self.path)
        
        # Convert to RGB if needed (handles RGBA, P mode, etc.)
        if self.original.mode not in ('RGB', 'L'):
            self.original = self.original.convert('RGB')
        
        self.current = self.original.copy()
        self.history = [self.current.copy()]
        return self
    
    def get_current(self) -> Optional[Image.Image]:
        """Get current image"""
        return self.current
    
    def get_thumbnail(self, size: Tuple[int, int] = None) -> Optional[Image.Image]:
        """Get thumbnail of current image"""
        if not self.current:
            return None
        
        size = size or self.THUMBNAIL_SIZE
        thumb = self.current.copy()
        thumb.thumbnail(size, Image.Resampling.LANCZOS)
        return thumb
    
    def undo(self) -> bool:
        """Undo last operation"""
        if len(self.history) > 1:
            self.history.pop()
            self.current = self.history[-1].copy()
            return True
        return False
    
    def reset(self) -> 'PhotoEditor':
        """Reset to original image"""
        if self.original:
            self.current = self.original.copy()
            self.history = [self.current.copy()]
        return self
    
    def _save_history(self):
        """Save current state to history"""
        if self.current:
            self.history.append(self.current.copy())
            # Limit history size
            if len(self.history) > 20:
                self.history.pop(0)
    
    # =========================================================================
    # Rotation Operations
    # =========================================================================
    
    def rotate_left(self) -> 'PhotoEditor':
        """Rotate 90 degrees counter-clockwise"""
        if self.current:
            self.current = self.current.rotate(90, expand=True)
            self._save_history()
        return self
    
    def rotate_right(self) -> 'PhotoEditor':
        """Rotate 90 degrees clockwise"""
        if self.current:
            self.current = self.current.rotate(-90, expand=True)
            self._save_history()
        return self
    
    def rotate(self, degrees: float) -> 'PhotoEditor':
        """Rotate by arbitrary degrees"""
        if self.current:
            self.current = self.current.rotate(degrees, expand=True, 
                                               fillcolor='white')
            self._save_history()
        return self
    
    def flip_horizontal(self) -> 'PhotoEditor':
        """Flip horizontally (mirror)"""
        if self.current:
            self.current = ImageOps.mirror(self.current)
            self._save_history()
        return self
    
    def flip_vertical(self) -> 'PhotoEditor':
        """Flip vertically"""
        if self.current:
            self.current = ImageOps.flip(self.current)
            self._save_history()
        return self
    
    # =========================================================================
    # Crop Operations
    # =========================================================================
    
    def crop(self, left: int, top: int, right: int, bottom: int) -> 'PhotoEditor':
        """Crop to specified region"""
        if self.current:
            self.current = self.current.crop((left, top, right, bottom))
            self._save_history()
        return self
    
    def crop_center(self, width: int, height: int) -> 'PhotoEditor':
        """Crop to center region of specified size"""
        if self.current:
            img_width, img_height = self.current.size
            left = (img_width - width) // 2
            top = (img_height - height) // 2
            right = left + width
            bottom = top + height
            self.current = self.current.crop((left, top, right, bottom))
            self._save_history()
        return self
    
    def crop_square(self) -> 'PhotoEditor':
        """Crop to square (centered)"""
        if self.current:
            width, height = self.current.size
            size = min(width, height)
            self.crop_center(size, size)
        return self
    
    def auto_crop(self, border: int = 0) -> 'PhotoEditor':
        """Auto-crop whitespace from edges"""
        if self.current:
            # Get bounding box of non-white pixels
            bbox = self.current.getbbox()
            if bbox:
                if border > 0:
                    bbox = (
                        max(0, bbox[0] - border),
                        max(0, bbox[1] - border),
                        min(self.current.width, bbox[2] + border),
                        min(self.current.height, bbox[3] + border)
                    )
                self.current = self.current.crop(bbox)
                self._save_history()
        return self
    
    # =========================================================================
    # Enhancement Operations
    # =========================================================================
    
    def brightness(self, factor: float) -> 'PhotoEditor':
        """
        Adjust brightness
        
        Args:
            factor: 0.0 = black, 1.0 = original, 2.0 = 2x brighter
        """
        if self.current:
            enhancer = ImageEnhance.Brightness(self.current)
            self.current = enhancer.enhance(factor)
            self._save_history()
        return self
    
    def contrast(self, factor: float) -> 'PhotoEditor':
        """
        Adjust contrast
        
        Args:
            factor: 0.0 = gray, 1.0 = original, 2.0 = 2x contrast
        """
        if self.current:
            enhancer = ImageEnhance.Contrast(self.current)
            self.current = enhancer.enhance(factor)
            self._save_history()
        return self
    
    def saturation(self, factor: float) -> 'PhotoEditor':
        """
        Adjust color saturation
        
        Args:
            factor: 0.0 = grayscale, 1.0 = original, 2.0 = 2x saturation
        """
        if self.current:
            enhancer = ImageEnhance.Color(self.current)
            self.current = enhancer.enhance(factor)
            self._save_history()
        return self
    
    def sharpness(self, factor: float) -> 'PhotoEditor':
        """
        Adjust sharpness
        
        Args:
            factor: 0.0 = blurred, 1.0 = original, 2.0 = 2x sharp
        """
        if self.current:
            enhancer = ImageEnhance.Sharpness(self.current)
            self.current = enhancer.enhance(factor)
            self._save_history()
        return self
    
    def auto_enhance(self) -> 'PhotoEditor':
        """Apply automatic enhancement for product photos"""
        if self.current:
            # Slight contrast boost
            self.contrast(1.1)
            # Slight brightness boost
            self.brightness(1.05)
            # Sharpen
            self.sharpness(1.2)
        return self
    
    # =========================================================================
    # Filter Operations
    # =========================================================================
    
    def blur(self, radius: float = 2) -> 'PhotoEditor':
        """Apply gaussian blur"""
        if self.current:
            self.current = self.current.filter(ImageFilter.GaussianBlur(radius))
            self._save_history()
        return self
    
    def sharpen(self) -> 'PhotoEditor':
        """Apply sharpen filter"""
        if self.current:
            self.current = self.current.filter(ImageFilter.SHARPEN)
            self._save_history()
        return self
    
    def denoise(self) -> 'PhotoEditor':
        """Apply median filter to reduce noise"""
        if self.current:
            self.current = self.current.filter(ImageFilter.MedianFilter(3))
            self._save_history()
        return self
    
    # =========================================================================
    # Resize Operations
    # =========================================================================
    
    def resize(self, width: int, height: int) -> 'PhotoEditor':
        """Resize to exact dimensions"""
        if self.current:
            self.current = self.current.resize((width, height), 
                                               Image.Resampling.LANCZOS)
            self._save_history()
        return self
    
    def resize_for_ebay(self) -> 'PhotoEditor':
        """Resize to optimal eBay size (max 1600px, min 500px)"""
        if self.current:
            width, height = self.current.size
            
            # Scale up if too small
            if width < self.EBAY_MIN_SIZE[0] or height < self.EBAY_MIN_SIZE[1]:
                scale = max(self.EBAY_MIN_SIZE[0] / width, 
                           self.EBAY_MIN_SIZE[1] / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                self.resize(new_width, new_height)
            
            # Scale down if too large
            elif width > self.EBAY_MAX_SIZE[0] or height > self.EBAY_MAX_SIZE[1]:
                self.current.thumbnail(self.EBAY_MAX_SIZE, Image.Resampling.LANCZOS)
                self._save_history()
        
        return self
    
    def add_white_background(self) -> 'PhotoEditor':
        """Add white background (useful for transparent images)"""
        if self.current:
            if self.current.mode == 'RGBA':
                background = Image.new('RGB', self.current.size, (255, 255, 255))
                background.paste(self.current, mask=self.current.split()[3])
                self.current = background
                self._save_history()
        return self
    
    # =========================================================================
    # Save Operations
    # =========================================================================
    
    def save(self, path: Optional[str] = None, quality: int = 95) -> Path:
        """
        Save current image
        
        Args:
            path: Output path (defaults to overwriting original)
            quality: JPEG quality (1-100)
            
        Returns:
            Path to saved file
        """
        if not self.current:
            raise ValueError("No image to save")
        
        save_path = Path(path) if path else self.path
        if not save_path:
            raise ValueError("No save path specified")
        
        # Ensure RGB mode for JPEG
        if save_path.suffix.lower() in ['.jpg', '.jpeg'] and self.current.mode != 'RGB':
            self.current = self.current.convert('RGB')
        
        self.current.save(save_path, quality=quality, optimize=True)
        return save_path
    
    def save_as(self, path: str, quality: int = 95) -> Path:
        """Save to new path"""
        return self.save(path, quality)
    
    def get_bytes(self, format: str = 'JPEG', quality: int = 95) -> bytes:
        """Get image as bytes"""
        if not self.current:
            raise ValueError("No image")
        
        buf = io.BytesIO()
        self.current.save(buf, format=format, quality=quality)
        return buf.getvalue()
    
    # =========================================================================
    # Info
    # =========================================================================
    
    def get_size(self) -> Tuple[int, int]:
        """Get current image size"""
        return self.current.size if self.current else (0, 0)
    
    def get_info(self) -> dict:
        """Get image information"""
        if not self.current:
            return {}
        
        return {
            'width': self.current.width,
            'height': self.current.height,
            'mode': self.current.mode,
            'format': self.current.format if hasattr(self.current, 'format') else None,
            'path': str(self.path) if self.path else None,
        }


def batch_process(folder_path: str, operations: List[str]) -> int:
    """
    Apply operations to all images in a folder
    
    Args:
        folder_path: Path to folder with images
        operations: List of operation names to apply
        
    Returns:
        Number of images processed
    """
    folder = Path(folder_path)
    extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
    
    count = 0
    for ext in extensions:
        for img_path in folder.glob(f'*{ext}'):
            try:
                editor = PhotoEditor(str(img_path))
                
                for op in operations:
                    if op == 'auto_enhance':
                        editor.auto_enhance()
                    elif op == 'resize_for_ebay':
                        editor.resize_for_ebay()
                    elif op == 'crop_square':
                        editor.crop_square()
                    elif op == 'sharpen':
                        editor.sharpen()
                
                editor.save()
                count += 1
                
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
    
    return count


# Test
if __name__ == "__main__":
    print("Testing Photo Editor...")
    
    # Create a test image
    test_img = Image.new('RGB', (800, 600), color='lightblue')
    test_path = Path(__file__).parent / "test_image.jpg"
    test_img.save(test_path)
    
    # Test operations
    editor = PhotoEditor(str(test_path))
    
    print(f"Original size: {editor.get_size()}")
    
    editor.rotate_right()
    print(f"After rotate: {editor.get_size()}")
    
    editor.brightness(1.2)
    editor.contrast(1.1)
    
    editor.undo()
    print("Undo successful")
    
    editor.reset()
    print("Reset successful")
    
    # Cleanup
    test_path.unlink()
    
    print("\n✅ Photo Editor working!")
