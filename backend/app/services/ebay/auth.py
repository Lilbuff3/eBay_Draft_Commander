"""
eBay OAuth Setup - Complete User Authorization
Uses official eBay OAuth methodology with proper RuName configuration
"""
import os
import requests
import base64
import time
import threading
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from backend.app.core.logger import get_logger

logger = get_logger('ebay_auth')

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
    
    # Class-level lock to prevent race conditions between background thread and reactive 401 refresh
    _refresh_lock = threading.Lock()
    
    def __init__(self, use_sandbox=True):
        """
        Initialize eBay OAuth client
        Args:
            use_sandbox: If True, use sandbox credentials/endpoints. If False, use production.
        """
        
        # Load environment variables from .env file
        from dotenv import load_dotenv, find_dotenv
        self.env_path = Path(find_dotenv())
        load_dotenv(self.env_path)
        
        # Load eBay credentials from environment
        self.app_id = os.getenv('EBAY_APP_ID')
        self.cert_id = os.getenv('EBAY_CERT_ID')
        self.ru_name = os.getenv('EBAY_RU_NAME') # Corrected from EBAY_RUNAME to EBAY_RU_NAME
        self.refresh_token = os.getenv('EBAY_REFRESH_TOKEN')
        
        if not all([self.app_id, self.cert_id]):
            logger.error("Missing required eBay credentials (APP_ID, CERT_ID) in .env file")
            raise ValueError("eBay credentials not found in environment")
        
        # Configure endpoints based on environment
        self.use_sandbox = use_sandbox
        if use_sandbox:
            self.oauth_endpoint = 'https://auth.sandbox.ebay.com/oauth2/authorize'
            self.token_endpoint = 'https://api.sandbox.ebay.com/identity/v1/oauth2/token'
        else:
            self.oauth_endpoint = 'https://auth.ebay.com/oauth2/authorize'
            self.token_endpoint = 'https://api.ebay.com/identity/v1/oauth2/token'
        
        self.access_token = None
        self.token_expiry = None
        
        logger.info(f"eBay OAuth initialized ({'Sandbox' if use_sandbox else 'Production'} mode)")
        
        # Local callback server settings (kept from original)
        self.callback_port = 8888
        self.callback_path = "/callback"
        self.authorization_code = None
        
    # Removed load_credentials method as it's replaced by dotenv
        
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
        
        return f"{self.oauth_endpoint}?" + urllib.parse.urlencode(params)
    
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
            response = requests.post(self.token_endpoint, headers=headers, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self.user_token = token_data['access_token']
                self.refresh_token = token_data.get('refresh_token')
                
                logger.info("Successfully obtained user token!")
                logger.info(f"   Access Token: ****...{self.user_token[-4:]}")
                logger.info(f"   Expires in: {token_data.get('expires_in', 'unknown')} seconds")
                
                if self.refresh_token:
                    logger.info(f"   Refresh Token: ****...{self.refresh_token[-4:]}")
                
                # Save tokens
                self.save_tokens()
                return True
            else:
                logger.error(f"Failed to get token: {response.status_code}")
                logger.error(f"   Error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error exchanging code: {e}")
            return False
    
    def refresh_access_token(self):
        """Refresh expired access token (Thread-Safe)"""
        # 1. Acquire Lock
        with self._refresh_lock:
            # 2. Re-load environment to get latest token (in case another thread just updated it)
            load_dotenv(self.env_path, override=True)
            self.refresh_token = os.getenv('EBAY_REFRESH_TOKEN')
            
            if not self.refresh_token:
                logger.error("No refresh token available")
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
                response = requests.post(self.token_endpoint, headers=headers, data=data)
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.user_token = token_data['access_token']
                    
                    # Update refresh token if rotated
                    if 'refresh_token' in token_data:
                         self.refresh_token = token_data['refresh_token']
                    
                    logger.info("Token refreshed successfully!")
                    self.save_tokens()
                    return True
                else:
                    logger.error(f"Refresh failed: {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error refreshing: {e}")
                return False
    
    def save_tokens(self):
        """Save tokens to .env file"""
        lines = []
        if self.env_path.exists():
            with open(self.env_path, 'r') as f:
                lines = f.readlines()
        
        # Consolidate user token variables
        token_vars = ['EBAY_USER_TOKEN', 'EBAY_USER_ACCESS_TOKEN']
        refresh_vars = ['EBAY_REFRESH_TOKEN', 'EBAY_USER_REFRESH_TOKEN']
        
        token_found = {v: False for v in token_vars}
        refresh_found = {v: False for v in refresh_vars}
        
        new_lines = []
        for line in lines:
            updated = False
            for v in token_vars:
                if line.startswith(f"{v}="):
                    new_lines.append(f"{v}={self.user_token}\n")
                    token_found[v] = True
                    updated = True
                    break
            if updated: continue
            
            for v in refresh_vars:
                if line.startswith(f"{v}="):
                    new_lines.append(f"{v}={self.refresh_token}\n")
                    refresh_found[v] = True
                    updated = True
                    break
            if updated: continue
            
            new_lines.append(line)
        
        # Add missing vars
        if self.user_token and not any(token_found.values()):
            new_lines.append(f"EBAY_USER_TOKEN={self.user_token}\n")
        if self.refresh_token and not any(refresh_found.values()):
            new_lines.append(f"EBAY_REFRESH_TOKEN={self.refresh_token}\n")
        
        with open(self.env_path, 'w') as f:
            f.writelines(new_lines)
        
        logger.info("Tokens saved to .env")
    
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
            logger.error("No code provided")
            return False


def main():
    print("eBay OAuth Setup")
    print("="*50)
    
    oauth = eBayOAuth(use_sandbox=False)  # Production
    
    if oauth.has_valid_token():
        print("\n✅ User token already configured!")
        print(f"   Token: ****...{oauth.user_token[-4:]}")
        
        refresh = input("\nRefresh token? (y/n): ").strip().lower()
        if refresh == 'y':
            oauth.refresh_access_token()
    else:
        print("\n⚠️ No user token found. Starting authorization...")
        oauth.start_auth_flow()


if __name__ == "__main__":
    main()
