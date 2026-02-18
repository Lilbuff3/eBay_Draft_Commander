"""
McpClient Service
Manages connection to the ebay-mcp server and executes tools.
"""
import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

# MCP Imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.app.core.logger import get_logger

logger = get_logger('mcp_client')

class McpClientService:
    """
    Client service for interacting with the ebay-mcp server.
    """
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.server_process = None
        self._lock = asyncio.Lock()
        
    async def connect(self):
        """Establish connection to ebay-mcp server"""
        if self.session:
            return

        logger.info("Connecting to ebay-mcp server...")
        
        # Determine path to ebay-mcp executable/script
        # Assuming ebay-mcp is installed globally or accessible via npx
        # Or specifically located in the user's workspace
        
        # Hardcoded path for this specific user setup based on previous context
        # "C:\Users\adam\OneDrive\Documents\Desktop\ebay mcp\ebay-mcp"
        
        project_root = Path(__file__).resolve().parents[4] # Adjust as needed based on where this file is
        # Actually, let's look for it relative to known locations or use npx
        
        ebay_mcp_path = Path("C:/Users/adam/OneDrive/Documents/Desktop/ebay mcp/ebay-mcp")
        
        server_params = None
        
        if ebay_mcp_path.exists():
             logger.info(f"Found local ebay-mcp at {ebay_mcp_path}")
             # Use node directly to run the build
             server_params = StdioServerParameters(
                command="node",
                args=[str(ebay_mcp_path / "build" / "index.js")],
                env=os.environ.copy()
            )
        else:
            logger.warning("Local ebay-mcp not found, attempting npx...")
            server_params = StdioServerParameters(
                command="npx",
                args=["-y", "ebay-mcp"],
                env=os.environ.copy()
            )

        try:
            # We need to maintain the context manager or handle lifecycle manually
            # The python SDK is designed for async context managers. 
            # For a long-running service, we might need a wrapper.
            
            # Since we can't easily keep the context manager open in a synchronous Flask app,
            # We will use a "connect-on-demand" approach for each request or a background loop.
            # But for simplicity in this implementation, we'll wrap the tool execution.
            pass

        except Exception as e:
            logger.error(f"Failed to connect to ebay-mcp: {e}")
            raise e

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Execute a tool on the ebay-mcp server.
        """
        if arguments is None:
            arguments = {}

        # Re-defining connection logic per-call for robustness in this context
        # In a production app, we'd have a persistent connection manager
        
        ebay_mcp_path = Path("C:/Users/adam/OneDrive/Documents/Desktop/ebay mcp/ebay-mcp")
        
        if ebay_mcp_path.exists():
             command = "node"
             args = [str(ebay_mcp_path / "build" / "index.js")]
        else:
             command = "npx"
             args = ["-y", "ebay-mcp"]
             
        # Check env vars
        from dotenv import load_dotenv
        # Try loading from project root explicitly
        project_root = Path(__file__).resolve().parents[3]
        env_path = project_root / '.env'
        load_dotenv(dotenv_path=env_path)
        
        env = os.environ.copy()
        
        # logical mapping from Draft Commander config names to ebay-mcp names
        if not env.get('EBAY_CLIENT_ID') and env.get('EBAY_APP_ID'):
            env['EBAY_CLIENT_ID'] = env.get('EBAY_APP_ID')
        if not env.get('EBAY_CLIENT_SECRET') and env.get('EBAY_CERT_ID'):
            env['EBAY_CLIENT_SECRET'] = env.get('EBAY_CERT_ID')
        if not env.get('EBAY_REDIRECT_URI') and env.get('EBAY_RU_NAME'):
            env['EBAY_REDIRECT_URI'] = env.get('EBAY_RU_NAME')
        
        # Set production environment (credentials are PRD-prefixed)
        if not env.get('EBAY_ENVIRONMENT'):
            env['EBAY_ENVIRONMENT'] = 'production'
            
        # Debug logging
        logger.info(f"Env vars check: EBAY_APP_ID={'Found' if env.get('EBAY_APP_ID') else 'Missing'}, EBAY_CLIENT_ID={'Found' if env.get('EBAY_CLIENT_ID') else 'Missing'}")

        # Verify essential vars are present
        required_vars = ['EBAY_CLIENT_ID', 'EBAY_CLIENT_SECRET', 'EBAY_REDIRECT_URI']
        missing = [v for v in required_vars if not env.get(v)]
        if missing:
             logger.warning(f"Missing environment variables for ebay-mcp: {missing}")

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Discover tools (optional, but good for verification)
                    # tools = await session.list_tools()
                    
                    # Execute
                    result = await session.call_tool(tool_name, arguments)
                    return result

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            raise e

    def run_tool_sync(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Synchronous wrapper for tool execution (for Flask)
        """
        return asyncio.run(self.execute_tool(tool_name, arguments))

# Singleton instance
_client = None

def get_mcp_client():
    global _client
    if _client is None:
        _client = McpClientService()
    return _client
