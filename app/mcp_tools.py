import os
import json
import sys
from pathlib import Path
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).resolve().parent.parent / "mcp_server" / "server.py"


class MCPToolBridge:
    def __init__(self, stack: AsyncExitStack, session: ClientSession):
        self.stack = stack
        self.session = session

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self.session.call_tool(name, arguments)
        values = []
        for item in result.content:
            text = getattr(item, "text", None)
            if text:
                try:
                    values.append(json.loads(text))
                except json.JSONDecodeError:
                    values.append(text)
        if len(values) == 1:
            return values[0]
        return values


@asynccontextmanager
async def mcp_session():
    async with AsyncExitStack() as stack:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER)],
            env={**os.environ},
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        yield MCPToolBridge(stack, session)

async def discover_candidates(requirements: dict) -> list[dict]:
    role = requirements.get("role") or "software developer"
    skills = requirements.get("skills") or []
    location = requirements.get("location") or ""
    query = " ".join([role, *skills[:5], location]).strip()
    github_query = " ".join([*skills[:3], location]).strip() or role
    found: list[dict] = []

    async with mcp_session() as bridge:
        for tool_name, arguments in [
            ("github_search_users", {"query": github_query, "per_page": 10}),
            ("public_web_search", {
                "query": f'{query} developer portfolio GitHub',
                "max_results": 8
            }),
        ]:
            try:
                data = await bridge.call_tool(tool_name, arguments)
                if isinstance(data, list):
                    found.extend(item for item in data if isinstance(item, dict))
                elif isinstance(data, dict):
                    found.append(data)
            except Exception as exc:
                found.append({"title": f"{tool_name} error", "snippet": str(exc)})
    # Deduplicate URLs
    unique = {}
    for item in found:
        key = item.get("profile_url") or item.get("url") or item.get("username")
        if key:
            unique[key] = item
    return list(unique.values())
