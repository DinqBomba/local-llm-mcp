import asyncio
from fastmcp import Client

async def main():
    client = Client("http://localhost:8000/mcp")

    async with client:
        tools = await client.list_tools()
        print("Available tools:")
        for t in tools:
            print(f"  - {t.name}: {t.description}")

        result = await client.call_tool(
            "web_search",
            {"query": "linux kernel", "limit": 3}
        )
        print("\nSearch result:")
        print(result)

asyncio.run(main())
