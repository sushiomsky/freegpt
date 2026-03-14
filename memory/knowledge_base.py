"""Lightweight knowledge base backed by SQLite.

Documents are stored as plain text.  A simple TF-IDF-inspired keyword search
is used so that the bot can retrieve relevant context without requiring a
vector-database dependency.  For production use this can be swapped for a
proper embedding-based store (e.g. ChromaDB) while keeping the same interface.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

_CREATE_DOCS_TABLE = """
CREATE TABLE IF NOT EXISTS kb_documents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    tags       TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_FTS_INDEX = "CREATE INDEX IF NOT EXISTS idx_kb_title ON kb_documents(title);"


def _tokenize(text: str) -> list[str]:
    """Very simple tokeniser: lower-case alpha-numeric tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _tfidf_score(query_tokens: list[str], doc_content: str) -> float:
    """Compute a simple TF-IDF-like relevance score."""
    doc_tokens = _tokenize(doc_content)
    if not doc_tokens:
        return 0.0
    tf = Counter(doc_tokens)
    doc_len = len(doc_tokens)
    score = 0.0
    for token in query_tokens:
        score += tf.get(token, 0) / doc_len
    return score


class KnowledgeBase:
    """Store and retrieve knowledge documents."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_DOCS_TABLE)
            await db.execute(_CREATE_FTS_INDEX)
            await db.commit()

    # ── public API ─────────────────────────────────────────────────────────────

    async def add_document(
        self,
        title: str,
        content: str,
        tags: Optional[list[str]] = None,
    ) -> int:
        """Insert a document and return its new id."""
        tag_str = ",".join(tags or [])
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "INSERT INTO kb_documents (title, content, tags) VALUES (?, ?, ?)",
                (title, content, tag_str),
            )
            await db.commit()
            return cursor.lastrowid

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return the *top_k* most relevant documents for *query*."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT id, title, content, tags FROM kb_documents"
            ) as cursor:
                rows = await cursor.fetchall()

        scored = [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "tags": row[3].split(",") if row[3] else [],
                "score": _tfidf_score(query_tokens, row[1] + " " + row[2]),
            }
            for row in rows
        ]
        scored.sort(key=lambda d: d["score"], reverse=True)
        return [d for d in scored[:top_k] if d["score"] > 0]

    async def get_document(self, doc_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT id, title, content, tags FROM kb_documents WHERE id = ?",
                (doc_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "tags": row[3].split(",") if row[3] else [],
        }

    async def delete_document(self, doc_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM kb_documents WHERE id = ?", (doc_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def list_documents(self, limit: int = 50) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT id, title, tags, created_at FROM kb_documents ORDER BY id DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "title": row[1],
                "tags": row[2].split(",") if row[2] else [],
                "created_at": row[3],
            }
            for row in rows
        ]
