"""
eBay Image Uploader - Using correct Media API endpoint
Uploads images to eBay Picture Services
"""
import requests
from pathlib import Path

def load_env():
    env_path = Path(__file__).parent / ".env"
    credentials = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                credentials[key.strip()] = value.strip()
    return credentials

credentials = load_env()
USER_TOKEN = credentials.get('EBAY_USER_TOKEN')

# Correct endpoint for 2026
MEDIA_URL = 'https://apim.ebay.com/commerce/media/v1_beta/image'


def upload_image_from_file(image_path):
    """
    Upload an image file to eBay Picture Services
    
    Uses multipart/form-data as required by the API
    
    Args:
        image_path: Path to the image file
    
    Returns:
        EPS image URL if successful, None otherwise
    """
    image_path = Path(image_path)
    
    if not image_path.exists():
        print(f"   ❌ File not found: {image_path}")
        return None
    
    # Determine content type
    suffix = image_path.suffix.lower()
    content_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    content_type = content_types.get(suffix, 'image/jpeg')
    
    print(f"   📷 Uploading {image_path.name}...")
    
    # Use multipart/form-data as required
    with open(image_path, 'rb') as f:
        files = {
            'file': (image_path.name, f, content_type)
        }
        
        headers = {
            'Authorization': 'Bearer ' + USER_TOKEN,
            'Accept': 'application/json'
        }
        
        response = requests.post(
            MEDIA_URL + '/create_image_from_file',
            headers=headers,
            files=files
        )
    
    print(f"      Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        # Get image_id from Location header
        location = response.headers.get('Location', '')
        
        if location:
            # Extract image_id from the location
            image_id = location.split('/')[-1]
            print(f"      Image ID: {image_id}")
            
            # Get the actual EPS URL
            eps_url = get_image_url(image_id)
            if eps_url:
                return eps_url
        
        # Try parsing response body
        if response.text:
            try:
                data = response.json()
                return data.get('imageUrl') or data.get('image', {}).get('imageUrl')
            except:
                pass
    
    print(f"      ❌ Error: {response.text[:200]}")
    return None


def get_image_url(image_id):
    """Get the EPS URL for an uploaded image"""
    headers = {
        'Authorization': 'Bearer ' + USER_TOKEN,
        'Accept': 'application/json'
    }
    
    response = requests.get(
        f'{MEDIA_URL}/{image_id}',
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        return data.get('imageUrl')
    
    return None


def upload_image_from_url(source_url):
    """
    Upload an image from a URL to eBay Picture Services
    
    Args:
        source_url: HTTPS URL of the image
    
    Returns:
        EPS image URL if successful, None otherwise
    """
    headers = {
        'Authorization': 'Bearer ' + USER_TOKEN,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    print(f"   📷 Uploading from URL...")
    
    response = requests.post(
        MEDIA_URL + '/create_image_from_url',
        headers=headers,
        json={'imageUrl': source_url}
    )
    
    print(f"      Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        # Get image_id from Location header
        location = response.headers.get('Location', '')
        
        if location:
            image_id = location.split('/')[-1]
            eps_url = get_image_url(image_id)
            if eps_url:
                return eps_url
        
        # Try parsing response
        if response.text:
            try:
                data = response.json()
                return data.get('imageUrl') or data.get('image', {}).get('imageUrl')
            except:
                pass
    
    print(f"      ❌ Error: {response.text[:200]}")
    return None


def upload_folder_images(folder_path, max_images=12):
    """
    Upload all images from a folder
    
    Args:
        folder_path: Path to folder containing images
        max_images: Maximum number of images (eBay limit is 12)
    
    Returns:
        List of EPS URLs
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        print(f"❌ Folder not found: {folder_path}")
        return []
    
    # Find image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    images = [f for f in folder_path.iterdir() 
              if f.suffix.lower() in image_extensions]
    
    if not images:
        print(f"❌ No images found in {folder_path}")
        return []
    
    # Sort by name
    images.sort(key=lambda x: x.name)
    
    # Limit to max
    images = images[:max_images]
    
    print(f"\n📷 Uploading {len(images)} images from {folder_path.name}")
    
    eps_urls = []
    for img in images:
        url = upload_image_from_file(img)
        if url:
            eps_urls.append(url)
    
    print(f"\n✅ Uploaded {len(eps_urls)}/{len(images)} images")
    
    return eps_urls


# Test
if __name__ == "__main__":
    # Test with SVBONY images
    folder = Path(r"C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\svbony_scope")
    
    if folder.exists():
        # Test single image first
        images = list(folder.glob("*.jpg"))
        if images:
            print(f"Testing upload of: {images[0].name}")
            url = upload_image_from_file(images[0])
            
            if url:
                print(f"\n✅ Success! EPS URL: {url}")
            else:
                print("\n❌ Upload failed")
    else:
        print(f"Folder not found: {folder}")
