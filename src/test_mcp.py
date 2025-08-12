import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_server():
    server_params = StdioServerParameters(
        command="python",
        args=["/workspaces/agent-trader/src/duckduckgo_mcp_server/server.py"],
        env={"PYTHONPATH": "/workspaces/agent-trader"}
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            # List available tools
            tools_result = await session.list_tools()
            print("Available tools:")
            # Access the tools list from the ListToolsResult object
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description.strip()}")
                print(f"    Input schema: {json.dumps(tool.inputSchema, indent=6)}")
            
            # Test search
            print("\nTesting search...")
            try:
                result = await session.call_tool("search", {"query": "Bitcoin price today", "max_results": 3})
                print(f"Search results: {result}")
            except Exception as e:
                print(f"Error calling search: {e}")
            
            # Test fetch_content
            print("\nTesting fetch_content...")
            try:
                result = await session.call_tool("fetch_content", {"url": "https://example.com"})
                # The result might be an object with a 'result' attribute
                if hasattr(result, 'result'):
                    content = result.result
                else:
                    content = str(result)
                print(f"Fetched content (first 200 chars): {content[:200]}...")
            except Exception as e:
                print(f"Error calling fetch_content: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_server())