from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from app.config import get_settings
from app.research.url_safety import URLSafetyError, validate_public_http_url
from app.schemas.source import WebPageContent
from app.tools.search_tool import run_web_search

logger = logging.getLogger(__name__)

USER_AGENT = "LocalResearchAI/0.1 (+research bot; respects robots.txt)"


def _strip_noise(soup: BeautifulSoup) -> None:
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
        tag.decompose()


def _extract_main_text(soup: BeautifulSoup) -> tuple[str, list[str], list[str]]:
    root = soup.find("article") or soup.find("main") or soup.body or soup
    headings = [h.get_text(" ", strip=True) for h in root.find_all(re.compile("^h[1-4]$"))][:20]
    paragraphs = [p.get_text(" ", strip=True) for p in root.find_all("p") if p.get_text(strip=True)][:80]
    if not paragraphs:
        text = root.get_text("\n", strip=True)
        paragraphs = [line for line in text.splitlines() if len(line) > 40][:80]
    text = "\n\n".join(paragraphs)
    return text, headings, paragraphs


def fetch_webpage(url: str) -> WebPageContent:
    settings = get_settings()
    try:
        safe_url = validate_public_http_url(url)
    except URLSafetyError as exc:
        return WebPageContent(url=url, fetch_error=str(exc))

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    try:
        with httpx.Client(timeout=settings.http_timeout_sec, follow_redirects=True, headers=headers) as client:
            resp = client.get(safe_url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return WebPageContent(url=safe_url, fetch_error=f"Unsupported content type: {content_type}")
            raw = resp.content[: settings.max_page_bytes]
            soup = BeautifulSoup(raw, "html.parser")
            _strip_noise(soup)
            title = (soup.title.string if soup.title and soup.title.string else "") or ""
            text, headings, paragraphs = _extract_main_text(soup)
            if len(text) < 80:
                return WebPageContent(url=safe_url, title=title, fetch_error="Insufficient extractable text")
            return WebPageContent(
                url=safe_url,
                title=title.strip(),
                headings=headings,
                paragraphs=paragraphs,
                text=text[:120_000],
            )
    except httpx.HTTPError as exc:
        logger.warning("Fetch failed %s: %s", url, exc)
        return WebPageContent(url=url, fetch_error=str(exc))


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the public web for information related to a query."""
    items = run_web_search(query, max_results=max_results)
    if not items:
        return "No results found."
    lines = [f"- {i.title} | {i.url} | {i.snippet[:200]}" for i in items]
    return "\n".join(lines)


@tool
def fetch_webpage_tool(url: str) -> str:
    """Fetch and extract readable text from a public webpage URL."""
    page = fetch_webpage(url)
    if page.fetch_error:
        return f"Error: {page.fetch_error}"
    preview = page.text[:4000]
    return f"Title: {page.title}\nURL: {page.url}\n\n{preview}"
