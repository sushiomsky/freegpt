"""Ollama LLM provider.

Connects to a locally running `Ollama <https://ollama.com>`_ instance that
hosts an *abliterated* (uncensored) model such as those produced by the
NousResearch llm-abliteration technique.

Reference: https://github.com/NousResearch/llm-abliteration
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

import httpx

from .base import LLMProvider, Message

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120.0  # seconds – local inference can be slow


class OllamaProvider(LLMProvider):
    """Chat with a local model served by Ollama."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    # ── public API ─────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[Message],
        *,
        stream: bool = False,
    ) -> str:
        if stream:
            chunks: list[str] = []
            async for chunk in self.stream_chat(messages):
                chunks.append(chunk)
            return "".join(chunks)

        payload = {
            "model": self._model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    async def stream_chat(
        self,
        messages: list[Message],
    ) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                import json as _json

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if data.get("done"):
                        break

    async def list_models(self) -> list[str]:
        """Return names of models available in the local Ollama instance."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self._base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
