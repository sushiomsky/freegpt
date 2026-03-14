"""Tests for the plugin system."""

from __future__ import annotations

import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure the project root is on sys.path so we can import project modules.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from plugins.base import Plugin, PluginResult
from plugins.registry import PluginRegistry


# ── Helpers ──────────────────────────────────────────────────────────────────

class _EchoPlugin(Plugin):
    name = "echo"
    description = "Echoes args back."
    usage = "<text>"

    async def execute(self, args: str, **context) -> PluginResult:
        return PluginResult(success=True, data=args)


# ── PluginResult ─────────────────────────────────────────────────────────────

class TestPluginResult(unittest.TestCase):
    def test_str_success(self):
        r = PluginResult(success=True, data="hello")
        self.assertEqual(str(r), "hello")

    def test_str_success_none(self):
        r = PluginResult(success=True)
        self.assertEqual(str(r), "OK")

    def test_str_failure(self):
        r = PluginResult(success=False, error="oops")
        self.assertEqual(str(r), "Error: oops")


# ── PluginRegistry ────────────────────────────────────────────────────────────

class TestPluginRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = PluginRegistry()

    def test_register_and_get(self):
        p = _EchoPlugin()
        self.registry.register(p)
        self.assertIs(self.registry.get("echo"), p)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.registry.get("nonexistent"))

    def test_all_plugins(self):
        self.registry.register(_EchoPlugin())
        self.assertEqual(len(self.registry.all_plugins()), 1)

    def test_help_lines(self):
        self.registry.register(_EchoPlugin())
        lines = self.registry.help_lines()
        self.assertTrue(any("echo" in line for line in lines))

    def test_load_by_name_not_found(self):
        result = self.registry.load_by_name("no_such_plugin_xyz")
        self.assertIsNone(result)

    def test_load_by_name_success(self):
        """Dynamically build a fake module and register it."""
        fake_module = types.ModuleType("plugins.fake_plugin")

        class FakePlugin(Plugin):
            name = "fake"
            description = "Fake"
            usage = ""

            async def execute(self, args: str, **ctx) -> PluginResult:
                return PluginResult(success=True, data="fake")

        fake_module.FakePlugin = FakePlugin
        sys.modules["plugins.fake_plugin"] = fake_module

        result = self.registry.load_by_name("fake")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "fake")

        del sys.modules["plugins.fake_plugin"]


# ── BrowsePlugin (unit, no network) ──────────────────────────────────────────

class TestBrowsePlugin(unittest.IsolatedAsyncioTestCase):
    async def test_empty_args(self):
        from plugins.browse_plugin import BrowsePlugin
        p = BrowsePlugin()
        result = await p.execute("")
        self.assertFalse(result.success)
        self.assertIn("URL", result.error)

    async def test_invalid_scheme(self):
        from plugins.browse_plugin import BrowsePlugin
        p = BrowsePlugin()
        result = await p.execute("ftp://example.com/file.txt")
        self.assertFalse(result.success)
        self.assertIn("scheme", result.error)

    async def test_successful_fetch(self):
        from plugins.browse_plugin import BrowsePlugin
        import httpx

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("plugins.browse_plugin.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            p = BrowsePlugin()
            result = await p.execute("https://example.com")

        self.assertTrue(result.success)
        self.assertIn("Hello World", result.data)


# ── MCPPlugin (unit, no network) ──────────────────────────────────────────────

class TestMCPPlugin(unittest.IsolatedAsyncioTestCase):
    async def test_empty_args(self):
        from plugins.mcp_plugin import MCPPlugin
        p = MCPPlugin()
        result = await p.execute("")
        self.assertFalse(result.success)

    async def test_invalid_json(self):
        from plugins.mcp_plugin import MCPPlugin
        p = MCPPlugin()
        result = await p.execute("search not-valid-json")
        self.assertFalse(result.success)
        self.assertIn("JSON", result.error)

    async def test_successful_call(self):
        from plugins.mcp_plugin import MCPPlugin

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"jsonrpc": "2.0", "id": "1", "result": {"content": "pong"}}
        )

        with patch("plugins.mcp_plugin.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            p = MCPPlugin()
            result = await p.execute('ping {}')

        self.assertTrue(result.success)
        self.assertEqual(result.data, "pong")


if __name__ == "__main__":
    unittest.main()
