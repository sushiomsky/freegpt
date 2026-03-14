"""Tests for the LLM layer."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from llm.base import Message
from llm.ollama_provider import OllamaProvider


class TestMessage(unittest.TestCase):
    def test_to_dict(self):
        m = Message(role="user", content="hello")
        self.assertEqual(m.to_dict(), {"role": "user", "content": "hello"})


class TestOllamaProvider(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.provider = OllamaProvider(
            base_url="http://localhost:11434", model="test-model"
        )

    def test_model_name(self):
        self.assertEqual(self.provider.model_name, "test-model")

    async def test_chat_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "message": {"role": "assistant", "content": "Hello!"},
                "done": True,
            }
        )

        with patch("llm.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await self.provider.chat(
                [Message(role="user", content="Hi")]
            )
        self.assertEqual(result, "Hello!")

    async def test_list_models(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "models": [{"name": "llama3"}, {"name": "mistral"}]
            }
        )

        with patch("llm.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            models = await self.provider.list_models()

        self.assertEqual(models, ["llama3", "mistral"])


if __name__ == "__main__":
    unittest.main()
