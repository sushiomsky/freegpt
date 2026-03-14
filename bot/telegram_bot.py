"""Telegram bot lifecycle management."""

from __future__ import annotations

import functools
import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from llm.ollama_provider import OllamaProvider
from memory.chat_manager import ChatManager
from memory.knowledge_base import KnowledgeBase
from plugins.code_editor_plugin import CodeEditorPlugin
from plugins.registry import PluginRegistry
from bot.handlers import (
    cmd_help,
    cmd_kb_add,
    cmd_kb_list,
    cmd_kb_search,
    cmd_models,
    cmd_new,
    cmd_start,
    cmd_stats,
    handle_message,
    handle_plugin_command,
)

logger = logging.getLogger(__name__)


def _build_app() -> Application:
    """Create and wire up the Telegram Application."""

    # ── Services ──────────────────────────────────────────────────────────────
    llm = OllamaProvider(base_url=config.OLLAMA_BASE_URL, model=config.OLLAMA_MODEL)
    chat_mgr = ChatManager(db_path=config.KB_DB_PATH)
    kb = KnowledgeBase(db_path=config.KB_DB_PATH)

    # ── Plugin registry ───────────────────────────────────────────────────────
    registry = PluginRegistry()

    for plugin_name in config.ENABLED_PLUGINS:
        if plugin_name == "mcp":
            # MCP plugin needs the server URL from config.
            from plugins.mcp_plugin import MCPPlugin
            registry.register(MCPPlugin(server_url=config.MCP_SERVER_URL))
        elif plugin_name == "code_editor":
            registry.register(
                CodeEditorPlugin(
                    api_key=config.COPILOT_API_KEY,
                    base_url=config.COPILOT_BASE_URL,
                    model=config.COPILOT_MODEL,
                    project_root=config.PROJECT_ROOT,
                )
            )
        else:
            registry.load_by_name(plugin_name)

    # ── Application ───────────────────────────────────────────────────────────
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # ── Core command handlers ─────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(
        CommandHandler("help", functools.partial(cmd_help, registry=registry))
    )
    app.add_handler(
        CommandHandler("new", functools.partial(cmd_new, chat_manager=chat_mgr))
    )
    app.add_handler(
        CommandHandler("stats", functools.partial(cmd_stats, chat_manager=chat_mgr))
    )
    app.add_handler(
        CommandHandler("models", functools.partial(cmd_models, llm_provider=llm))
    )
    app.add_handler(
        CommandHandler(
            "kb_add",
            functools.partial(cmd_kb_add, knowledge_base=kb),
        )
    )
    app.add_handler(
        CommandHandler(
            "kb_search",
            functools.partial(cmd_kb_search, knowledge_base=kb),
        )
    )
    app.add_handler(
        CommandHandler(
            "kb_list",
            functools.partial(cmd_kb_list, knowledge_base=kb),
        )
    )

    # ── Dynamic plugin command handlers ───────────────────────────────────────
    for plugin in registry.all_plugins():
        app.add_handler(
            CommandHandler(
                plugin.name,
                functools.partial(
                    handle_plugin_command,
                    plugin_name=plugin.name,
                    registry=registry,
                    knowledge_base=kb,
                    chat_manager=chat_mgr,
                ),
            )
        )

    # ── Plain-text message handler ────────────────────────────────────────────
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            functools.partial(
                handle_message,
                llm_provider=llm,
                chat_manager=chat_mgr,
                knowledge_base=kb,
                registry=registry,
            ),
        )
    )

    # ── Post-init: DB setup & bot menu ───────────────────────────────────────
    async def _post_init(application: Application) -> None:
        await chat_mgr.init()
        await kb.init()
        commands = [
            BotCommand("start", "Introduction"),
            BotCommand("help", "List commands"),
            BotCommand("new", "Reset conversation"),
            BotCommand("stats", "Conversation statistics"),
            BotCommand("models", "List local models"),
            BotCommand("kb_add", "Add knowledge-base document"),
            BotCommand("kb_search", "Search knowledge base"),
            BotCommand("kb_list", "List knowledge-base documents"),
        ]
        for plugin in registry.all_plugins():
            commands.append(BotCommand(plugin.name, plugin.description[:64]))
        await application.bot.set_my_commands(commands)
        logger.info("Bot initialised. Model: %s", config.OLLAMA_MODEL)

    app.post_init = _post_init

    return app


def run() -> None:
    """Build the app and start polling."""
    app = _build_app()
    logger.info("Starting FreeGPT bot…")
    app.run_polling(allowed_updates=["message"])
