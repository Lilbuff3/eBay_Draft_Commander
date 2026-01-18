"""
eBay Picture Services (EPS) Upload - Trading API Fallback
Uses UploadSiteHostedPictures which works until Sept 2026
"""
import requests
import base64
import xml.etree.ElementTree as ET
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

TRADING_API_URL = 'https://api.ebay.com/ws/api.dll'


def upload_image_trading_api(image_path):
    """
    Upload image to EPS using Trading API UploadSiteHostedPictures
    
    Args:
        image_path: Path to image file
    
    Returns:
        EPS URL if successful, None otherwise
    """
    image_path = Path(image_path)
    
    if not image_path.exists():
        print(f"   ❌ File not found: {image_path}")
        return None
    
    print(f"   📷 Uploading {image_path.name} via Trading API...")
    
    # Read and encode image
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Create XML payload
    xml_payload = f'''<?xml version="1.0" encoding="utf-8"?>
<UploadSiteHostedPicturesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{USER_TOKEN}</eBayAuthToken>
    </RequesterCredentials>
    <PictureName>{image_path.name}</PictureName>
    <PictureSet>Supersize</PictureSet>
    <ExtensionInDays>365</ExtensionInDays>
</UploadSiteHostedPicturesRequest>'''
    
    # Determine content type
    suffix = image_path.suffix.lower()
    content_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif'
    }
    content_type = content_types.get(suffix, 'image/jpeg')
    
    # Build multipart form data manually
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    
    body = b''
    # XML part
    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="XML Payload"\r\n'
    body += b'Content-Type: text/xml\r\n\r\n'
    body += xml_payload.encode('utf-8')
    body += b'\r\n'
    
    # Image part
    body += f'--{boundary}\r\n'.encode()
    body += f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'.encode()
    body += f'Content-Type: {content_type}\r\n\r\n'.encode()
    body += image_data
    body += b'\r\n'
    body += f'--{boundary}--\r\n'.encode()
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'X-EBAY-API-SITEID': '0',
        'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
        'X-EBAY-API-CALL-NAME': 'UploadSiteHostedPictures',
        'Authorization': 'Bearer ' + USER_TOKEN
    }
    
    response = requests.post(TRADING_API_URL, headers=headers, data=body)
    
    print(f"      Status: {response.status_code}")
    
    if response.status_code == 200:
        # Parse XML response
        try:
            root = ET.fromstring(response.text)
            
            # Check for errors
            ack = root.find('.//{urn:ebay:apis:eBLBaseComponents}Ack')
            if ack is not None and ack.text in ['Success', 'Warning']:
                # Get the EPS URL
                full_url = root.find('.//{urn:ebay:apis:eBLBaseComponents}FullURL')
                if full_url is not None and full_url.text:
                    print(f"      ✅ EPS URL: {full_url.text[:60]}...")
                    return full_url.text
            
            # Check for errors
            errors = root.findall('.//{urn:ebay:apis:eBLBaseComponents}Errors')
            for error in errors:
                msg = error.find('{urn:ebay:apis:eBLBaseComponents}LongMessage')
                if msg is not None:
                    print(f"      ❌ Error: {msg.text}")
        except Exception as e:
            print(f"      ❌ Parse error: {e}")
            print(f"      Response: {response.text[:500]}")
    else:
        print(f"      ❌ Error: {response.text[:300]}")
    
    return None


def upload_folder(folder_path, max_images=12):
    """Upload all images from a folder"""
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        print(f"❌ Folder not found: {folder_path}")
        return []
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif'}
    images = [f for f in folder_path.iterdir() if f.suffix.lower() in image_extensions]
    images.sort(key=lambda x: x.name)
    images = images[:max_images]
    
    if not images:
        print(f"❌ No images in {folder_path}")
        return []
    
    print(f"\n📷 Uploading {len(images)} images from {folder_path.name}")
    
    eps_urls = []
    for img in images:
        url = upload_image_trading_api(img)
        if url:
            eps_urls.append(url)
    
    print(f"\n✅ Uploaded {len(eps_urls)}/{len(images)} images")
    return eps_urls


# Test
if __name__ == "__main__":
    folder = Path(r"C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\svbony_scope")
    
    if folder.exists():
        images = list(folder.glob("*.jpg"))
        if images:
            print(f"Testing with: {images[0].name}")
            url = upload_image_trading_api(images[0])
            
            if url:
                print(f"\n🎉 SUCCESS! Image uploaded to EPS")
                print(f"   URL: {url}")
            else:
                print("\n❌ Upload failed")
    else:
        print(f"Folder not found: {folder}")
