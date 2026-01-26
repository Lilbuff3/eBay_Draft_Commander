"""
eBay OAuth Setup - Complete User Authorization
Uses official eBay OAuth methodology with proper RuName configuration
"""
import os
import base64
import webbrowser
import urllib.parse
import requests
import json
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

class eBayOAuth:
    """Complete eBay OAuth implementation"""
    
    # eBay Production endpoints
    AUTH_URL_PROD = "https://auth.ebay.com/oauth2/authorize"
    TOKEN_URL_PROD = "https://api.ebay.com/identity/v1/oauth2/token"
    
    # eBay Sandbox endpoints  
    AUTH_URL_SANDBOX = "https://auth.sandbox.ebay.com/oauth2/authorize"
    TOKEN_URL_SANDBOX = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    
    # Required scopes for creating listings
    SCOPES = [
        "https://api.ebay.com/oauth/api_scope",
        "https://api.ebay.com/oauth/api_scope/sell.inventory",
        "https://api.ebay.com/oauth/api_scope/sell.account",
        "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    ]
    
    def __init__(self, use_sandbox=False):
        self.env_path = Path(__file__).resolve().parents[4] / ".env"
        self.load_credentials()
        
        self.use_sandbox = use_sandbox
        self.auth_url = self.AUTH_URL_SANDBOX if use_sandbox else self.AUTH_URL_PROD
        self.token_url = self.TOKEN_URL_SANDBOX if use_sandbox else self.TOKEN_URL_PROD
        
        # Local callback server settings
        self.callback_port = 8888
        self.callback_path = "/callback"
        self.authorization_code = None
        
    def load_credentials(self):
        """Load credentials from .env"""
        credentials = {}
        if self.env_path.exists():
            with open(self.env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        credentials[key.strip()] = value.strip()
        
        self.app_id = credentials.get('EBAY_APP_ID')
        self.cert_id = credentials.get('EBAY_CERT_ID')
        self.ru_name = credentials.get('EBAY_RU_NAME')
        self.user_token = credentials.get('EBAY_USER_TOKEN')
        self.refresh_token = credentials.get('EBAY_REFRESH_TOKEN')
        
        print(f"✅ Loaded App ID: {self.app_id[:20]}..." if self.app_id else "❌ No App ID")
        print(f"✅ RuName: {self.ru_name}" if self.ru_name else "⚠️ No RuName configured")
        
    def get_authorization_url(self):
        """Generate the authorization URL for user consent"""
        if not self.ru_name:
            # Use eBay's default if no RuName
            redirect_uri = "https://signin.ebay.com/authorize"
        else:
            redirect_uri = self.ru_name
            
        params = {
            'client_id': self.app_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self.SCOPES),
            'prompt': 'login',  # Force fresh login
        }
        
        return f"{self.auth_url}?" + urllib.parse.urlencode(params)
    
    def exchange_code_for_token(self, auth_code):
        """Exchange authorization code for access token"""
        credentials = f"{self.app_id}:{self.cert_id}"
        encoded = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {encoded}'
        }
        
        # Determine redirect URI
        if self.ru_name:
            redirect_uri = self.ru_name
        else:
            redirect_uri = "https://signin.ebay.com/authorize"
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': redirect_uri
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.user_token = token_data['access_token']
                self.refresh_token = token_data.get('refresh_token')
                
                print("\n✅ Successfully obtained user token!")
                print(f"   Access Token: {self.user_token[:50]}...")
                print(f"   Expires in: {token_data.get('expires_in', 'unknown')} seconds")
                
                if self.refresh_token:
                    print(f"   Refresh Token: {self.refresh_token[:30]}...")
                
                # Save tokens
                self.save_tokens()
                return True
            else:
                print(f"\n❌ Failed to get token: {response.status_code}")
                print(f"   Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"\n❌ Error exchanging code: {e}")
            return False
    
    def refresh_access_token(self):
        """Refresh expired access token"""
        if not self.refresh_token:
            print("❌ No refresh token available")
            return False
            
        credentials = f"{self.app_id}:{self.cert_id}"
        encoded = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {encoded}'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'scope': ' '.join(self.SCOPES)
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.user_token = token_data['access_token']
                
                print("✅ Token refreshed successfully!")
                self.save_tokens()
                return True
            else:
                print(f"❌ Refresh failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error refreshing: {e}")
            return False
    
    def save_tokens(self):
        """Save tokens to .env file"""
        lines = []
        if self.env_path.exists():
            with open(self.env_path, 'r') as f:
                lines = f.readlines()
        
        # Update tokens
        token_updated = False
        refresh_updated = False
        new_lines = []
        
        for line in lines:
            if line.startswith('EBAY_USER_TOKEN='):
                new_lines.append(f'EBAY_USER_TOKEN={self.user_token}\n')
                token_updated = True
            elif line.startswith('EBAY_REFRESH_TOKEN='):
                new_lines.append(f'EBAY_REFRESH_TOKEN={self.refresh_token}\n')
                refresh_updated = True
            else:
                new_lines.append(line)
        
        if not token_updated and self.user_token:
            new_lines.append(f'EBAY_USER_TOKEN={self.user_token}\n')
        if not refresh_updated and self.refresh_token:
            new_lines.append(f'EBAY_REFRESH_TOKEN={self.refresh_token}\n')
        
        with open(self.env_path, 'w') as f:
            f.writelines(new_lines)
        
        print("✅ Tokens saved to .env")
    
    def has_valid_token(self):
        """Check if we have a user token"""
        return bool(self.user_token)
    
    def start_auth_flow(self):
        """Interactive authorization flow"""
        print("\n" + "="*70)
        print("🔐 eBay OAuth User Authorization")
        print("="*70)
        
        if not self.ru_name:
            print("\n⚠️  IMPORTANT: You need to set up your RuName first!")
            print("\nSteps to get your RuName:")
            print("1. Go to: https://developer.ebay.com/my/keys")
            print("2. Click on your Production app (Image Lister)")
            print("3. Scroll to 'User Tokens' section")
            print("4. Click 'Get a Token from eBay via Your Application'")
            print("5. If not set up, click 'Add eBay Redirect URL'")
            print("   - Accept URL: https://signin.ebay.com/authorize")
            print("   - Decline URL: https://signin.ebay.com/authorize")
            print("   - Display Title: Image Lister")
            print("   - Privacy Policy: https://example.com/privacy")
            print("6. After saving, you'll see your RuName")
            print("\nThen add this line to your .env file:")
            print("   EBAY_RU_NAME=your-runame-here")
            print("\n" + "-"*70)
            
            # Try with default redirect
            print("\nAttempting with eBay's default redirect URL...")
        
        url = self.get_authorization_url()
        
        print(f"\n📌 Opening browser for authorization...")
        print(f"\nIf browser doesn't open, go to this URL manually:\n")
        print(url[:100] + "...\n")
        
        webbrowser.open(url)
        
        print("-"*70)
        print("\nAfter you authorize, you'll be redirected.")
        print("Look for '?code=' in the URL and copy everything after it.")
        print("(Stop at the first '&' if there are more parameters)\n")
        
        auth_code = input("Paste the authorization code here: ").strip()
        
        if auth_code:
            # Clean up the code (remove any URL encoding issues)
            auth_code = auth_code.split('&')[0]  # Remove any trailing params
            return self.exchange_code_for_token(auth_code)
        else:
            print("❌ No code provided")
            return False


def main():
    print("eBay OAuth Setup")
    print("="*50)
    
    oauth = eBayOAuth(use_sandbox=False)  # Production
    
    if oauth.has_valid_token():
        print("\n✅ User token already configured!")
        print(f"   Token: {oauth.user_token[:30]}...")
        
        refresh = input("\nRefresh token? (y/n): ").strip().lower()
        if refresh == 'y':
            oauth.refresh_access_token()
    else:
        print("\n⚠️ No user token found. Starting authorization...")
        oauth.start_auth_flow()


if __name__ == "__main__":
    main()
