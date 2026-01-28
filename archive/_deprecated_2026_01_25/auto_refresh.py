
from ebay_auth import eBayOAuth
import sys

def refresh():
    print("🔄 Auto-refreshing eBay Token...")
    oauth = eBayOAuth(use_sandbox=False)
    if oauth.refresh_access_token():
        print("✅ Token refreshed and saved to .env")
        sys.exit(0)
    else:
        print("❌ Failed to refresh token")
        sys.exit(1)

if __name__ == "__main__":
    refresh()
