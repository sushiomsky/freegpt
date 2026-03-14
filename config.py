"""Central configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
import pathlib
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _get_list(key: str) -> list[str]:
    raw = _get(key)
    return [item.strip() for item in raw.split(",") if item.strip()] if raw else []


# ── Telegram ───────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = _get("TELEGRAM_BOT_TOKEN")

ALLOWED_USER_IDS: list[int] = [int(uid) for uid in _get_list("ALLOWED_USER_IDS") if uid.isdigit()]

# ── Local LLM ─────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = _get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = _get("OLLAMA_MODEL", "llama3")

# ── Knowledge Base ────────────────────────────────────────────────────────────
KB_DB_PATH: str = _get("KB_DB_PATH", "freegpt.db")

# ── Plugins ───────────────────────────────────────────────────────────────────
ENABLED_PLUGINS: list[str] = _get_list("ENABLED_PLUGINS")

# ── MCP ───────────────────────────────────────────────────────────────────────
MCP_SERVER_URL: str = _get("MCP_SERVER_URL", "http://localhost:3000")

# ── Code-editor plugin ────────────────────────────────────────────────────────
COPILOT_API_KEY: str = _get("COPILOT_API_KEY")
COPILOT_BASE_URL: str = _get("COPILOT_BASE_URL", "https://api.openai.com/v1")
COPILOT_MODEL: str = _get("COPILOT_MODEL", "gpt-4o")

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = _get("LOG_LEVEL", "INFO").upper()

# ── Project root (needed by code-editor plugin) ───────────────────────────────
PROJECT_ROOT: pathlib.Path = pathlib.Path(__file__).parent.resolve()
