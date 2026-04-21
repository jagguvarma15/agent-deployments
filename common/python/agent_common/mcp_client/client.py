"""MCP (Model Context Protocol) client wrapper with connection management."""

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class MCPClient:
    """A lightweight MCP client wrapper.

    Usage:
        async with MCPClient(base_url="http://localhost:3001") as client:
            tools = await client.list_tools()
            result = await client.call_tool("search", {"query": "hello"})
    """

    base_url: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    _http_client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
            )
        return self._http_client

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server."""
        client = await self._get_client()
        response = await client.post("/list-tools", json={})
        response.raise_for_status()
        return response.json().get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool on the MCP server."""
        client = await self._get_client()
        response = await client.post(
            "/call-tool",
            json={"name": name, "arguments": arguments or {}},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "MCPClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
