"""Abstract base class and result type for all plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PluginResult:
    """Encapsulates the output of a plugin invocation."""

    success: bool
    data: Any = None
    error: Optional[str] = None

    def __str__(self) -> str:  # used when injecting tool output into the LLM context
        if self.success:
            return str(self.data) if self.data is not None else "OK"
        return f"Error: {self.error}"


class Plugin(ABC):
    """Every plugin must subclass this and implement ``execute``."""

    # Short name used in slash commands and the registry key.
    name: str = ""

    # Human-readable description shown in /help.
    description: str = ""

    # Usage hint shown in /help, e.g. "<query>".
    usage: str = ""

    @abstractmethod
    async def execute(self, args: str, **context: Any) -> PluginResult:
        """Run the plugin with *args* (raw text after the command).

        *context* may carry optional helpers like ``knowledge_base`` or
        ``chat_manager`` injected by the orchestrator.
        """

    def help_text(self) -> str:
        return f"/{self.name} {self.usage} – {self.description}"
