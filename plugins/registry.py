"""Dynamic plugin registry.

Plugins are discovered by name: the registry looks for a module called
``plugins.<name>_plugin`` and a class inside it whose ``name`` attribute
matches.

Built-in plugins can also be registered directly.
"""

from __future__ import annotations

import importlib
import logging
from typing import Optional

from .base import Plugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Keeps track of loaded plugins and provides a lookup interface."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    # ── registration ──────────────────────────────────────────────────────────

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        self._plugins[plugin.name] = plugin
        logger.info("Registered plugin: %s", plugin.name)

    def load_by_name(self, plugin_name: str) -> Optional[Plugin]:
        """Dynamically import ``plugins.<plugin_name>_plugin`` and register it.

        Returns the loaded :class:`Plugin` instance or ``None`` on failure.
        """
        module_path = f"plugins.{plugin_name}_plugin"
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:
            logger.error("Plugin module not found: %s", module_path)
            return None

        # Find the Plugin subclass inside the module.
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Plugin)
                and attr is not Plugin
                and getattr(attr, "name", "") == plugin_name
            ):
                instance = attr()
                self.register(instance)
                return instance

        logger.error(
            "No Plugin subclass with name=%r found in %s", plugin_name, module_path
        )
        return None

    # ── lookup ────────────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[Plugin]:
        return self._plugins.get(name)

    def all_plugins(self) -> list[Plugin]:
        return list(self._plugins.values())

    def help_lines(self) -> list[str]:
        return [p.help_text() for p in self.all_plugins()]
