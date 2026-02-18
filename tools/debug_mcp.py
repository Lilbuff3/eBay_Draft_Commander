import asyncio
import os
import json
from dotenv import load_dotenv
from pathlib import Path

# Load env same way as service
project_root = Path(__file__).resolve().parents[1]
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

# Add project root to path
import sys
sys.path.append(str(project_root))

from backend.app.services.mcp_client import get_mcp_client

async def main():
    print("McpClient Debug Tool")
    print(f"Project Root: {project_root}")
    
    # Check Env keys
    print("Environment Variables:")
    for k, v in os.environ.items():
        if 'EBAY' in k:
            masked = v[:4] + '...' + v[-4:] if v and len(v) > 8 else '***'
            print(f"  {k}: {masked}")
            
    client = get_mcp_client()
    
    print("\n1. Checking Token Status...")
    try:
        status = await client.execute_tool("ebay_get_token_status", {})
        print(f"Status Result: {status}")
        
        if status and hasattr(status, 'content'):
             data = json.loads(status.content[0].text)
             print(f"Token Data: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"Get Status Error: {e}")

    # Try setting tokens if available in env
    access = os.environ.get('EBAY_USER_TOKEN')
    refresh = os.environ.get('EBAY_REFRESH_TOKEN')
    
    if access and refresh:
        print("\n2. Found tokens in env. Attempting to set in ebay-mcp...")
        try:
            res = await client.execute_tool("ebay_set_user_tokens", {
                "accessToken": access,
                "refreshToken": refresh
            })
            print(f"Set Tokens Result: {res}")
        except Exception as e:
            print(f"Set Tokens Error: {e}")
    else:
        print("\nSkipping token set: Missing EBAY_USER_TOKEN or EBAY_REFRESH_TOKEN")

if __name__ == "__main__":
    asyncio.run(main())
