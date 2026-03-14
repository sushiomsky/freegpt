"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class Message:
    """A single chat message."""

    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class LLMProvider(ABC):
    """Interface that every LLM backend must implement."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        *,
        stream: bool = False,
    ) -> str:
        """Send *messages* and return the complete assistant reply as a string.

        When *stream* is ``True`` the implementation should still return the
        complete text (accumulated from the stream) so callers do not need to
        handle both modes.
        """

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive from the model."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the identifier of the currently configured model."""
