"""
eBay Picture Services Upload - CORRECTED Media API Endpoint
Based on validation via eBay API Test Tool (apim.ebay.com exists, api.ebay.com is 404)
"""
import requests
import json
from pathlib import Path
from backend.app.core.logger import get_logger

logger = get_logger('ebay_media')

import os
from dotenv import load_dotenv, find_dotenv

def load_env():
    """Load credentials from .env file using python-dotenv"""
    env_path = find_dotenv()
    if env_path:
        load_dotenv(env_path, override=True)

    # Return a dict for compatibility with existing code
    return {key: os.environ.get(key) for key in [
        'EBAY_USER_TOKEN'
    ]}

def _get_token():
    """Get a fresh eBay user token from .env (handles token rotation)"""
    creds = load_env()
    return creds.get('EBAY_USER_TOKEN', '')

# CONFIRMED via API Explorer: apim.ebay.com is the correct host for Media API
BASE_URL = 'https://apim.ebay.com/commerce/media/v1_beta'

def check_endpoint_reachability():
    """
    Sanity check: Hit the endpoint with correct host but wrong content type.
    Should return 415 (Unsupported Media Type).
    If it returns 404, the path/host is unresolved/wrong.
    """
    url = f'{BASE_URL}/image/create_image_from_file'
    logger.info(f"Reachability Test: {url}")

    headers = {
        'Authorization': 'Bearer ' + _get_token(),
        'Content-Type': 'application/json',  # Deliberately wrong
        'Accept': 'application/json'
    }
    
    try:
        r = requests.post(url, headers=headers, json={"test": "ping"})
        logger.info(f"   Status: {r.status_code}")
        
        if r.status_code == 415:
            logger.info("   ✅ Endpoint is REACHABLE (Correctly rejected JSON)")
            return True
        elif r.status_code == 404:
            logger.error("   ❌ Endpoint NOT FOUND (404)")
            return False
        else:
            logger.warning(f"   ⚠️ Unexpected status: {r.status_code} (But not 404, so likely reachable)")
            return True
            
    except Exception as e:
        logger.error(f"   ❌ Network/SSL Error: {e}")
        return False

def upload_image_to_eps(image_path):
    """
    Upload an image to eBay Picture Services (EPS)
    """
    image_path = Path(image_path)
    if not image_path.exists():
        logger.error(f"❌ File not found: {image_path}")
        return None
        
    url = f'{BASE_URL}/image/create_image_from_file'
    logger.info(f"📷 Uploading {image_path.name} to {url}")
    
    # MIME type detection
    suffix = image_path.suffix.lower()
    content_type = 'image/jpeg'
    if suffix == '.png': content_type = 'image/png'
    elif suffix == '.webp': content_type = 'image/webp'
    elif suffix == '.gif': content_type = 'image/gif'
    
    # Read file and prepare multipart upload
    with open(image_path, 'rb') as f:
        # NOTE: tuple format is (filename, file_object, content_type)
        files = {
            'image': (image_path.name, f, content_type)
        }
        
        headers = {
            'Authorization': 'Bearer ' + _get_token(),
            'Accept': 'application/json',
        }
        
        try:
            # RETRY LOOP for Auth Automation
            max_retries = 2
            for attempt in range(max_retries):
                r = requests.post(url, headers=headers, files=files, timeout=30)
                logger.info(f"   Status: {r.status_code}")
                
                # Check for Token Expiry (401)
                if r.status_code == 401 and attempt == 0:
                    logger.warning("   ⚠️ Token expired (401) during upload. Refreshing...")
                    try:
                        from backend.app.services.ebay.auth import eBayOAuth
                        oauth = eBayOAuth(use_sandbox=False)
                        if oauth.refresh_access_token():
                            # Reload fresh token from .env
                            new_token = _get_token()
                            if new_token:
                                headers['Authorization'] = f'Bearer {new_token}'
                                # Rewind file for retry
                                f.seek(0)
                                logger.info("   Retrying upload with new token...")
                                continue # Loop to retry
                    except Exception as e:
                        logger.error(f"   ❌ Refresh failed: {e}")
                
                # If we're here, it's either success, a non-401 error, or retry failed
                break
                
            if r.status_code in [200, 201]:
                data = r.json()
                # Try to find imageUrl
                eps_url = data.get('imageUrl') 
                
                # Sometimes it might be in Location header without body
                if not eps_url and 'Location' in r.headers:
                    logger.info(f"   Found Location header, fetching details...")
                    image_id = r.headers['Location'].split('/')[-1]
                    # Fetch details
                    r2 = requests.get(f'{BASE_URL}/image/{image_id}', headers=headers)
                    if r2.status_code == 200:
                        eps_url = r2.json().get('imageUrl')

                if eps_url:
                    logger.info(f"   ✅ SUCCESS: {eps_url}")
                    return eps_url
                else:
                    logger.warning(f"   ⚠️ Upload seemingly success but no URL found. Resp: {r.text}")
                    return None
            else:
                logger.error(f"   ❌ Failed. Response: {r.text}")
                return None
                
        except Exception as e:
            logger.error(f"   ❌ Exception: {e}")
            return None

def upload_folder(folder_path, max_images=12):
    """Upload all images from a folder"""
    folder_path = Path(folder_path)
    if not folder_path.exists():
        return []
        
    # Check reachability first
    if not check_endpoint_reachability():
        logger.error("❌ API Endpoint unreachable. Aborting upload.")
        return []
        
    images = [p for p in folder_path.glob("*") if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']]
    images = images[:max_images]
    
    urls = []
    logger.info(f"\nProcessing {len(images)} images from {folder_path}...")
    for img in images:
        url = upload_image_to_eps(img)
        if url:
            urls.append(url)
            
    return urls

# Self-test
if __name__ == "__main__":
    if check_endpoint_reachability():
        test_folder = Path(r"C:\Users\adam\Desktop\eBay_Draft_Commander\inbox\svbony_scope")
        if test_folder.exists():
            first_image = next(test_folder.glob("*.jpg"), None)
            if first_image:
                upload_image_to_eps(first_image)
