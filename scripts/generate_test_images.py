import os
from PIL import Image, ImageDraw, ImageFont

def create_test_images():
    base_dir = r"c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander\inbox\test_ifs_converter"
    os.makedirs(base_dir, exist_ok=True)
    
    for i in range(1, 6):
        img = Image.new('RGB', (800, 600), color=(73, 109, 137))
        d = ImageDraw.Draw(img)
        d.text((10,10), f"Test Image {i} - IFS Converter", fill=(255, 255, 0))
        
        filename = os.path.join(base_dir, f"image_{i}.jpg")
        img.save(filename)
        print(f"Created: {filename}")

if __name__ == "__main__":
    create_test_images()
