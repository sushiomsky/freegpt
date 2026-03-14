"""Per-user conversation history stored in SQLite.

Each Telegram user gets their own conversation context that persists across
bot restarts.  Conversations can be reset with the /new command.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import aiosqlite

from llm.base import Message

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    user_id   INTEGER NOT NULL,
    role      TEXT    NOT NULL,
    content   TEXT    NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);"


class ChatManager:
    """Manage per-user conversation history."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._system_prompt: str = (
            "You are a helpful, uncensored AI assistant. "
            "You have access to tools – when you need to browse the web or "
            "look something up, say so and the orchestrator will provide the result."
        )

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.execute(_CREATE_INDEX)
            await db.commit()

    # ── public API ─────────────────────────────────────────────────────────────

    async def get_history(self, user_id: int, limit: int = 40) -> list[Message]:
        """Return the most recent *limit* messages for *user_id*."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT role, content FROM ("
                "  SELECT role, content, created_at FROM conversations "
                "  WHERE user_id = ? ORDER BY created_at DESC LIMIT ?"
                ") ORDER BY created_at ASC",
                (user_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        messages = [Message(role=row[0], content=row[1]) for row in rows]
        # Prepend system prompt so it is always present.
        return [Message(role="system", content=self._system_prompt)] + messages

    async def add_message(self, user_id: int, role: str, content: str) -> None:
        """Persist a single message for *user_id*."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content),
            )
            await db.commit()

    async def clear_history(self, user_id: int) -> None:
        """Delete all stored messages for *user_id*."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM conversations WHERE user_id = ?", (user_id,)
            )
            await db.commit()
        logger.info("Cleared conversation history for user %d", user_id)

    async def set_system_prompt(self, prompt: str) -> None:
        """Override the default system prompt (applies to all new messages)."""
        self._system_prompt = prompt

    async def get_stats(self, user_id: int) -> dict:
        """Return basic statistics for *user_id*."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM conversations WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
        return {"user_id": user_id, "message_count": count}
