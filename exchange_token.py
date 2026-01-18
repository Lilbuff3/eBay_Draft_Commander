"""
Exchange authorization code for eBay user token
"""
import base64
import urllib.parse
import requests
from pathlib import Path

# Credentials
APP_ID = "AdamYous-ImageLis-PRD-a3c53308d-244bd56d"
CERT_ID = "PRD-c565a359d170-d13d-43dd-9994-b8a4"
RU_NAME = "Adam_Youssef-AdamYous-ImageL-zolhnoe"

# The authorization code (URL decoded)
AUTH_CODE_ENCODED = "v%5E1.1%23i%5E1%23I%5E3%23r%5E1%23p%5E3%23f%5E0%23t%5EUl41XzI6RkMzQjRCODI3NTA0NTU5NkIzOEVGNjM1Rjg0MTBFNENfMV8xI0VeMjYw"
AUTH_CODE = urllib.parse.unquote(AUTH_CODE_ENCODED)

print(f"Auth Code (decoded): {AUTH_CODE}")

# Create Basic Auth header
credentials = f"{APP_ID}:{CERT_ID}"
encoded = base64.b64encode(credentials.encode()).decode()

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': f'Basic {encoded}'
}

data = {
    'grant_type': 'authorization_code',
    'code': AUTH_CODE,
    'redirect_uri': RU_NAME
}

print("\nExchanging code for token...")

response = requests.post(
    "https://api.ebay.com/identity/v1/oauth2/token",
    headers=headers,
    data=data
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    token_data = response.json()
    
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token', '')
    
    print("\n✅ SUCCESS!")
    print(f"Access Token: {access_token[:50]}...")
    print(f"Expires in: {token_data.get('expires_in')} seconds")
    
    if refresh_token:
        print(f"Refresh Token: {refresh_token[:30]}...")
    
    # Save to .env
    env_path = Path(__file__).parent / ".env"
    with open(env_path, 'a') as f:
        f.write(f"\nEBAY_USER_TOKEN={access_token}\n")
        if refresh_token:
            f.write(f"EBAY_REFRESH_TOKEN={refresh_token}\n")
    
    print("\n✅ Tokens saved to .env!")
    
else:
    print(f"\n❌ Failed: {response.text}")
