# FreeGPT

A Telegram bot interface for **local, abliterated LLMs** (via [Ollama](https://ollama.com)) with agentic capabilities, a persistent knowledge base, and a decoupled plugin architecture.

> **Abliterated models** are uncensored local LLMs produced with the
> [NousResearch llm-abliteration](https://github.com/NousResearch/llm-abliteration)
> technique.  They run fully offline through Ollama.

---

## Features

| Category | Details |
|---|---|
| **Local LLM** | Connects to Ollama; any abliterated or standard model |
| **Chat management** | Per-user conversation history persisted in SQLite; `/new` to reset |
| **Knowledge base** | Add, search, and list documents; relevant docs injected into context automatically |
| **Plugin system** | Decoupled, dynamically loaded plugins via a registry |
| **Web browsing** | `browse` plugin fetches and parses web pages |
| **MCP tools** | `mcp` plugin calls any [Model Context Protocol](https://modelcontextprotocol.io) server (JSON-RPC 2.0) |
| **Self-modification** | `code_editor` plugin uses GitHub Copilot / OpenAI API to propose and apply changes to the bot's own code |
| **Access control** | Optional allowlist of Telegram user IDs |

---

## Architecture

```
freegpt/
├── main.py                     # Entry point
├── config.py                   # Config from env / .env file
├── bot/
│   ├── telegram_bot.py         # Bot lifecycle (start/stop, handler wiring)
│   └── handlers.py             # All Telegram command & message handlers
├── llm/
│   ├── base.py                 # Abstract LLMProvider + Message
│   └── ollama_provider.py      # Ollama backend (streaming + non-streaming)
├── memory/
│   ├── chat_manager.py         # Per-user conversation history (SQLite)
│   └── knowledge_base.py       # Document store with TF-IDF keyword search
├── plugins/
│   ├── base.py                 # Plugin + PluginResult base classes
│   ├── registry.py             # Dynamic plugin loader & registry
│   ├── browse_plugin.py        # Web page fetcher (httpx + BeautifulSoup)
│   ├── mcp_plugin.py           # MCP JSON-RPC client
│   └── code_editor_plugin.py   # Self-modification via Copilot/OpenAI API
└── tests/
    ├── test_llm.py
    ├── test_memory.py
    └── test_plugins.py
```

---

## Quick Start

### 1. Prerequisites

* Python ≥ 3.11
* [Ollama](https://ollama.com/download) running locally with an abliterated model pulled:
  ```bash
  ollama pull llama3          # or any NousResearch abliterated variant
  ```
* A Telegram bot token from [@BotFather](https://t.me/BotFather)

### 2. Install

```bash
git clone https://github.com/sushiomsky/freegpt.git
cd freegpt
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env – at minimum set TELEGRAM_BOT_TOKEN
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from BotFather |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Model name in Ollama |
| `ENABLED_PLUGINS` | *(empty)* | Comma-separated: `browse,mcp,code_editor` |
| `MCP_SERVER_URL` | `http://localhost:3000` | MCP server URL |
| `COPILOT_API_KEY` | *(required for code_editor)* | GitHub Copilot / OpenAI API key |
| `ALLOWED_USER_IDS` | *(empty = everyone)* | Comma-separated Telegram user IDs |

### 4. Run

```bash
python main.py
```

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Introduction |
| `/help` | List all commands including loaded plugins |
| `/new` | Clear current conversation history |
| `/stats` | Number of messages in your conversation |
| `/models` | List models available in Ollama |
| `/kb_add <title> \| <content>` | Save a document to the knowledge base |
| `/kb_search <query>` | Full-text search the knowledge base |
| `/kb_list` | List all knowledge-base documents |
| `/browse <url>` | *(browse plugin)* Fetch and summarise a web page |
| `/mcp <tool> <json_args>` | *(mcp plugin)* Call an MCP server tool |
| `/code_editor <file> <instruction>` | *(code_editor plugin)* Ask Copilot to modify a file |

---

## Writing Your Own Plugin

1. Create `plugins/myplugin_plugin.py`:

```python
from plugins.base import Plugin, PluginResult

class MypluginPlugin(Plugin):
    name = "myplugin"
    description = "Does something useful."
    usage = "<args>"

    async def execute(self, args: str, **context) -> PluginResult:
        return PluginResult(success=True, data=f"You said: {args}")
```

2. Add `myplugin` to `ENABLED_PLUGINS` in your `.env`.

The plugin is automatically discovered, registered, and wired to `/myplugin`.

---

## Testing

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

---

## Security Notes

* The `code_editor` plugin can **write files** – restrict it with `ALLOWED_USER_IDS`.
* The `browse` plugin only accepts `http`/`https` URLs.
* No secrets are ever committed; copy `.env.example` → `.env` and keep `.env` out of version control.
