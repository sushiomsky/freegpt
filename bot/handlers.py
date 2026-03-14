"""Telegram command and message handlers.

Each handler receives the standard ``(update, context)`` pair from
``python-telegram-bot`` and delegates to the appropriate service layer.
"""

from __future__ import annotations

import logging
from typing import Optional

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

import config
from llm.base import Message
from memory.chat_manager import ChatManager
from memory.knowledge_base import KnowledgeBase
from plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _is_allowed(user_id: int) -> bool:
    if not config.ALLOWED_USER_IDS:
        return True
    return user_id in config.ALLOWED_USER_IDS


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start."""
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ You are not authorised to use this bot.")
        return
    await update.message.reply_text(
        "👋 Hello! I'm *FreeGPT* – a local abliterated LLM Telegram interface.\n\n"
        "Commands:\n"
        "/help – list available commands and plugins\n"
        "/new – start a fresh conversation\n"
        "/kb_add <title> | <content> – add a knowledge-base document\n"
        "/kb_search <query> – search the knowledge base\n"
        "/kb_list – list knowledge-base documents\n"
        "/models – list available local models\n"
        "/stats – show conversation statistics\n\n"
        "Loaded plugins provide additional /commands listed in /help.",
        parse_mode="Markdown",
    )


async def cmd_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    registry: PluginRegistry,
) -> None:
    """Handle /help."""
    if not _is_allowed(update.effective_user.id):
        return

    lines = [
        "*FreeGPT – Help*",
        "",
        "*Core commands*",
        "/start – introduction",
        "/new – clear conversation history",
        "/stats – message count for this chat",
        "/models – list Ollama models",
        "/kb_add <title> | <content> – save a document",
        "/kb_search <query> – semantic search in the knowledge base",
        "/kb_list – list all saved documents",
    ]

    plugin_lines = registry.help_lines()
    if plugin_lines:
        lines += ["", "*Plugin commands*"] + plugin_lines

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_new(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_manager: ChatManager,
) -> None:
    """Handle /new – reset conversation."""
    if not _is_allowed(update.effective_user.id):
        return
    await chat_manager.clear_history(update.effective_user.id)
    await update.message.reply_text("🗑️ Conversation cleared. Let's start fresh!")


async def cmd_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_manager: ChatManager,
) -> None:
    """Handle /stats."""
    if not _is_allowed(update.effective_user.id):
        return
    stats = await chat_manager.get_stats(update.effective_user.id)
    await update.message.reply_text(
        f"📊 You have *{stats['message_count']}* messages in your conversation history.",
        parse_mode="Markdown",
    )


async def cmd_models(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    llm_provider,
) -> None:
    """Handle /models – list available Ollama models."""
    if not _is_allowed(update.effective_user.id):
        return
    try:
        models = await llm_provider.list_models()
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"⚠️ Could not reach Ollama: {exc}")
        return
    if not models:
        await update.message.reply_text("No models found in Ollama.")
        return
    lines = ["*Available models:*"] + [f"• `{m}`" for m in models]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_kb_add(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    knowledge_base: KnowledgeBase,
) -> None:
    """Handle /kb_add <title> | <content>."""
    if not _is_allowed(update.effective_user.id):
        return
    raw = " ".join(context.args) if context.args else ""
    if "|" not in raw:
        await update.message.reply_text(
            "Usage: /kb_add <title> | <content>", parse_mode="Markdown"
        )
        return
    title, _, content = raw.partition("|")
    title, content = title.strip(), content.strip()
    if not title or not content:
        await update.message.reply_text("Both title and content are required.")
        return
    doc_id = await knowledge_base.add_document(title=title, content=content)
    await update.message.reply_text(
        f"✅ Document saved (id={doc_id}).", parse_mode="Markdown"
    )


async def cmd_kb_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    knowledge_base: KnowledgeBase,
) -> None:
    """Handle /kb_search <query>."""
    if not _is_allowed(update.effective_user.id):
        return
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /kb_search <query>")
        return
    results = await knowledge_base.search(query)
    if not results:
        await update.message.reply_text("No matching documents found.")
        return
    lines = [f"*Found {len(results)} result(s):*"]
    for doc in results:
        snippet = doc["content"][:200].replace("\n", " ")
        lines.append(f"\n📄 *[{doc['id']}] {doc['title']}*\n{snippet}…")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_kb_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    knowledge_base: KnowledgeBase,
) -> None:
    """Handle /kb_list."""
    if not _is_allowed(update.effective_user.id):
        return
    docs = await knowledge_base.list_documents()
    if not docs:
        await update.message.reply_text("The knowledge base is empty.")
        return
    lines = [f"*Knowledge Base ({len(docs)} documents):*"]
    for doc in docs:
        tags = ", ".join(doc["tags"]) if doc["tags"] else "–"
        lines.append(f"• [{doc['id']}] {doc['title']} (tags: {tags})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    llm_provider,
    chat_manager: ChatManager,
    knowledge_base: KnowledgeBase,
    registry: PluginRegistry,
) -> None:
    """Handle plain text messages – the main LLM chat loop."""
    user = update.effective_user
    if not _is_allowed(user.id):
        await update.message.reply_text("⛔ Not authorised.")
        return

    user_text = update.message.text or ""
    if not user_text.strip():
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    # Retrieve relevant knowledge and prepend to history.
    kb_results = await knowledge_base.search(user_text, top_k=3)
    messages = await chat_manager.get_history(user.id)

    if kb_results:
        kb_context = "\n\n".join(
            f"[KB] {r['title']}: {r['content'][:500]}" for r in kb_results
        )
        messages.insert(
            1,  # right after system prompt
            Message(
                role="system",
                content=f"Relevant knowledge base context:\n{kb_context}",
            ),
        )

    messages.append(Message(role="user", content=user_text))

    # Save user message.
    await chat_manager.add_message(user.id, "user", user_text)

    try:
        reply = await llm_provider.chat(messages)
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM error for user %d", user.id)
        await update.message.reply_text(f"⚠️ LLM error: {exc}")
        return

    # Save assistant reply.
    await chat_manager.add_message(user.id, "assistant", reply)

    # Split long replies to respect Telegram's 4096-char limit.
    for chunk in _split_message(reply):
        await update.message.reply_text(chunk)


async def handle_plugin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    plugin_name: str,
    registry: PluginRegistry,
    knowledge_base: KnowledgeBase,
    chat_manager: ChatManager,
) -> None:
    """Dispatch a plugin slash-command."""
    user = update.effective_user
    if not _is_allowed(user.id):
        return
    plugin = registry.get(plugin_name)
    if plugin is None:
        await update.message.reply_text(f"Plugin '{plugin_name}' is not loaded.")
        return

    args = " ".join(context.args) if context.args else ""
    await update.message.chat.send_action(ChatAction.TYPING)

    result = await plugin.execute(
        args,
        knowledge_base=knowledge_base,
        chat_manager=chat_manager,
    )

    reply = str(result)
    for chunk in _split_message(reply):
        await update.message.reply_text(chunk)


# ── Utility ───────────────────────────────────────────────────────────────────

def _split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split *text* into chunks of at most *max_len* characters."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks
