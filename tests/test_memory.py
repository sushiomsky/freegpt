"""Tests for the memory layer (ChatManager & KnowledgeBase)."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import tempfile
import os


class TestChatManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from memory.chat_manager import ChatManager

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.mgr = ChatManager(db_path=self._tmp.name)
        await self.mgr.init()

    async def asyncTearDown(self):
        os.unlink(self._tmp.name)

    async def test_empty_history(self):
        history = await self.mgr.get_history(user_id=1)
        # Only system prompt present.
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].role, "system")

    async def test_add_and_retrieve(self):
        await self.mgr.add_message(1, "user", "Hello")
        await self.mgr.add_message(1, "assistant", "Hi there")
        history = await self.mgr.get_history(user_id=1)
        # system + user + assistant
        self.assertEqual(len(history), 3)
        self.assertEqual(history[1].role, "user")
        self.assertEqual(history[1].content, "Hello")

    async def test_clear_history(self):
        await self.mgr.add_message(1, "user", "Hello")
        await self.mgr.clear_history(1)
        history = await self.mgr.get_history(user_id=1)
        self.assertEqual(len(history), 1)  # only system prompt

    async def test_stats(self):
        await self.mgr.add_message(1, "user", "a")
        await self.mgr.add_message(1, "user", "b")
        stats = await self.mgr.get_stats(1)
        self.assertEqual(stats["message_count"], 2)

    async def test_isolation_between_users(self):
        await self.mgr.add_message(1, "user", "user1 message")
        await self.mgr.add_message(2, "user", "user2 message")
        h1 = await self.mgr.get_history(user_id=1)
        h2 = await self.mgr.get_history(user_id=2)
        self.assertEqual(len(h1), 2)  # system + 1 msg
        self.assertEqual(len(h2), 2)


class TestKnowledgeBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from memory.knowledge_base import KnowledgeBase

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.kb = KnowledgeBase(db_path=self._tmp.name)
        await self.kb.init()

    async def asyncTearDown(self):
        os.unlink(self._tmp.name)

    async def test_add_and_get(self):
        doc_id = await self.kb.add_document(
            title="Python basics",
            content="Python is a high-level programming language.",
        )
        self.assertIsNotNone(doc_id)
        doc = await self.kb.get_document(doc_id)
        self.assertEqual(doc["title"], "Python basics")

    async def test_search_returns_relevant(self):
        await self.kb.add_document(title="Python tutorial", content="Python variables loops functions")
        await self.kb.add_document(title="Cooking recipes", content="pasta tomato sauce cheese")
        results = await self.kb.search("Python programming")
        self.assertTrue(len(results) > 0)
        self.assertIn("Python", results[0]["title"])

    async def test_search_empty_query(self):
        results = await self.kb.search("")
        self.assertEqual(results, [])

    async def test_delete_document(self):
        doc_id = await self.kb.add_document(title="temp", content="temp content")
        deleted = await self.kb.delete_document(doc_id)
        self.assertTrue(deleted)
        self.assertIsNone(await self.kb.get_document(doc_id))

    async def test_delete_nonexistent(self):
        result = await self.kb.delete_document(99999)
        self.assertFalse(result)

    async def test_list_documents(self):
        await self.kb.add_document(title="doc1", content="content1")
        await self.kb.add_document(title="doc2", content="content2")
        docs = await self.kb.list_documents()
        self.assertGreaterEqual(len(docs), 2)


if __name__ == "__main__":
    unittest.main()
