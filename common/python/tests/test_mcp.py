"""Tests for mcp/client module."""

from mcp.client import MCPClient


def test_mcp_client_init():
    client = MCPClient(base_url="http://localhost:3001")
    assert client.base_url == "http://localhost:3001"
    assert client.timeout == 30.0


def test_mcp_client_custom_headers():
    client = MCPClient(
        base_url="http://localhost:3001",
        headers={"Authorization": "Bearer test"},
        timeout=60.0,
    )
    assert client.headers["Authorization"] == "Bearer test"
    assert client.timeout == 60.0
