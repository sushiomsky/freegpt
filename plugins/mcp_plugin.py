"""MCP (Model Context Protocol) client plugin.

Connects to an MCP server and forwards tool-call requests.  The MCP protocol
is JSON-RPC 2.0 over HTTP.

Reference spec: https://modelcontextprotocol.io/specification
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx

from .base import Plugin, PluginResult

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30.0


class MCPPlugin(Plugin):
    """Forward tool calls to a local MCP server."""

    name = "mcp"
    description = "Call an MCP server tool (JSON-RPC 2.0)."
    usage = '<tool_name> <json_args>'

    def __init__(self, server_url: str = "http://localhost:3000") -> None:
        self._server_url = server_url.rstrip("/")

    async def execute(self, args: str, **context: Any) -> PluginResult:
        """args format: ``<tool_name> <json_args>``

        Example: ``search {"query": "latest AI news"}``
        """
        parts = args.strip().split(None, 1)
        if not parts:
            return PluginResult(success=False, error="Usage: /mcp <tool_name> <json_args>")

        tool_name = parts[0]
        raw_params = parts[1] if len(parts) > 1 else "{}"

        try:
            params = json.loads(raw_params)
        except json.JSONDecodeError as exc:
            return PluginResult(success=False, error=f"Invalid JSON args: {exc}")

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": params},
        }

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.post(self._server_url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.RequestError as exc:
            return PluginResult(success=False, error=f"MCP request failed: {exc}")
        except httpx.HTTPStatusError as exc:
            return PluginResult(
                success=False,
                error=f"MCP server returned HTTP {exc.response.status_code}",
            )

        if "error" in data:
            return PluginResult(success=False, error=str(data["error"]))

        result = data.get("result", {})
        content = result.get("content", result)
        return PluginResult(success=True, data=content)

    async def list_tools(self) -> PluginResult:
        """Request the list of available tools from the MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/list",
            "params": {},
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.post(self._server_url, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            return PluginResult(success=False, error=str(exc))

        if "error" in data:
            return PluginResult(success=False, error=str(data["error"]))

        return PluginResult(success=True, data=data.get("result", {}).get("tools", []))
