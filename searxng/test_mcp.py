import asyncio
from fastmcp import Client

async def main():
    client = Client("http://localhost:8000/sse")

    async with client:
        result = await client.call_tool(
            "web_search",
            {"query": "linux kernel", "limit": 3}
        )

        print(result)

asyncio.run(main())
