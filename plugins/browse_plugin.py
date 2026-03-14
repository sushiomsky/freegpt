"""Web-browsing plugin.

Fetches a URL and returns a cleaned text representation.  The content can
then be injected into the LLM context so the model can answer questions about
the page.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .base import Plugin, PluginResult

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; freegpt/1.0; +https://github.com/sushiomsky/freegpt)"
    )
}
_MAX_CONTENT_CHARS = 8_000
_REQUEST_TIMEOUT = 20.0


def _clean_html(html: str) -> str:
    """Extract readable text from *html*."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove script / style / nav noise.
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse blank lines.
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text[:_MAX_CONTENT_CHARS]


class BrowsePlugin(Plugin):
    """Fetch a URL and return the readable page content."""

    name = "browse"
    description = "Fetch a web page and return its text content."
    usage = "<url>"

    async def execute(self, args: str, **context: Any) -> PluginResult:
        url = args.strip()
        if not url:
            return PluginResult(success=False, error="Please provide a URL.")

        # Basic validation.
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return PluginResult(
                success=False,
                error=f"Unsupported scheme: {parsed.scheme!r}. Only http/https are allowed.",
            )

        try:
            async with httpx.AsyncClient(
                headers=_HEADERS,
                follow_redirects=True,
                timeout=_REQUEST_TIMEOUT,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return PluginResult(
                success=False,
                error=f"HTTP {exc.response.status_code} for {url}",
            )
        except httpx.RequestError as exc:
            return PluginResult(success=False, error=f"Request failed: {exc}")

        content_type = response.headers.get("content-type", "")
        if "html" in content_type:
            text = _clean_html(response.text)
        else:
            text = response.text[:_MAX_CONTENT_CHARS]

        return PluginResult(success=True, data=text)
