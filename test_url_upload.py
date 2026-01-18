"""
Test EPS upload using createImageFromUrl
This uses an externally hosted image URL
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

MEDIA_URL = 'https://api.ebay.com/commerce/media/v1_beta/image'


def upload_from_url(image_url):
    """Upload an image from an external HTTPS URL to EPS"""
    
    headers = {
        'Authorization': 'Bearer ' + USER_TOKEN,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    payload = {
        'imageUrl': image_url
    }
    
    print(f"Uploading from: {image_url[:50]}...")
    
    response = requests.post(
        MEDIA_URL + '/create_image_from_url',
        headers=headers,
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    
    if response.status_code in [200, 201]:
        # Get Location header for image_id
        location = response.headers.get('Location', '')
        print(f"Location: {location}")
        
        if location:
            image_id = location.split('/')[-1]
            
            # Fetch the actual EPS URL
            get_resp = requests.get(
                f'{MEDIA_URL}/{image_id}',
                headers={'Authorization': 'Bearer ' + USER_TOKEN, 'Accept': 'application/json'}
            )
            
            if get_resp.status_code == 200:
                data = get_resp.json()
                eps_url = data.get('imageUrl')
                if eps_url:
                    print(f"\n✅ EPS URL: {eps_url}")
                    return eps_url
        
        # Try direct response
        if response.text:
            try:
                data = response.json()
                return data.get('imageUrl')
            except:
                pass
    
    return None


# Test with a known working image URL
if __name__ == "__main__":
    # Using a public image URL for testing
    test_url = "https://i.ebayimg.com/images/g/~D8AAOSwZ1dhmPT2/s-l1600.webp"  # Existing eBay image
    
    result = upload_from_url(test_url)
    
    if result:
        print(f"\n🎉 SUCCESS! Got EPS URL: {result}")
    else:
        print("\n❌ Failed")
