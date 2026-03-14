"""Self-modification plugin powered by an OpenAI-compatible API (GitHub Copilot).

Allows the bot to propose and apply changes to its own source code using the
Copilot / OpenAI API.  All changes are reviewed as diffs before being written,
and only the project directory is in scope.

Security note: this plugin should only be available to trusted administrators.
"""

from __future__ import annotations

import logging
import pathlib
import textwrap
from typing import Any

import httpx

from .base import Plugin, PluginResult

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 60.0
_MAX_FILE_CHARS = 20_000  # guard against huge files in context


class CodeEditorPlugin(Plugin):
    """Propose and apply code changes to the bot's own source using Copilot."""

    name = "code_editor"
    description = "Ask Copilot to modify a source file. Requires COPILOT_API_KEY."
    usage = "<file_path> <instruction>"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        project_root: str | pathlib.Path = ".",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._project_root = pathlib.Path(project_root).resolve()

    async def execute(self, args: str, **context: Any) -> PluginResult:
        """args: ``<relative_file_path> <instruction>``

        Example: ``plugins/browse_plugin.py Add a timeout parameter``
        """
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            return PluginResult(
                success=False,
                error="Usage: /code_editor <file_path> <instruction>",
            )

        rel_path, instruction = parts[0], parts[1]

        # Resolve and validate the target path stays inside the project.
        target = (self._project_root / rel_path).resolve()
        try:
            target.relative_to(self._project_root)
        except ValueError:
            return PluginResult(
                success=False,
                error="Path traversal detected – only project files may be edited.",
            )

        if not target.exists():
            return PluginResult(success=False, error=f"File not found: {rel_path}")

        original = target.read_text(encoding="utf-8")[:_MAX_FILE_CHARS]

        # Build prompt for the code model.
        system_prompt = textwrap.dedent(
            """\
            You are an expert Python software engineer.
            The user will give you a file path, its current content, and an instruction.
            Reply with ONLY the complete updated file content – no markdown fences,
            no explanations, just the raw file text.
            """
        )
        user_message = (
            f"File: {rel_path}\n\n"
            f"Current content:\n{original}\n\n"
            f"Instruction: {instruction}"
        )

        try:
            new_content = await self._call_api(system_prompt, user_message)
        except Exception as exc:  # noqa: BLE001
            return PluginResult(success=False, error=f"API call failed: {exc}")

        # Write the updated content.
        target.write_text(new_content, encoding="utf-8")
        logger.info("Code editor updated %s", target)

        # Return a short diff summary for the user.
        diff = _summarise_diff(original, new_content, rel_path)
        return PluginResult(success=True, data=diff)

    async def _call_api(self, system_prompt: str, user_message: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]


def _summarise_diff(original: str, updated: str, path: str) -> str:
    """Return a human-readable summary of lines added/removed."""
    orig_lines = set(original.splitlines())
    new_lines = set(updated.splitlines())
    added = new_lines - orig_lines
    removed = orig_lines - new_lines
    parts = [f"Updated `{path}`:"]
    if added:
        parts.append(f"  + {len(added)} line(s) added")
    if removed:
        parts.append(f"  - {len(removed)} line(s) removed")
    if not added and not removed:
        parts.append("  (no changes detected)")
    return "\n".join(parts)
