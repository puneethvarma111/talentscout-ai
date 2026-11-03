from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.ldr_prompts import SUMMARIZER_SYSTEM, current_date_str
from app.config import get_settings
from app.llm.ollama_client import get_chat_model
from app.schemas.source import SourceRecord, WebPageContent


def format_sources_for_summary(
    sources: list[SourceRecord],
    pages: dict[str, WebPageContent],
    *,
    fetch_full_page: bool,
    max_chars: int | None = None,
) -> str:
    settings = get_settings()
    limit = max_chars if max_chars is not None else settings.effective_summary_context_max_chars
    blocks: list[str] = []
    seen_urls: set[str] = set()
    for src in sources:
        url = src.url.rstrip("/")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        title = src.title or url
        snippet = (src.snippet or "")[:800]
        body = snippet
        page = pages.get(src.url) or pages.get(url)
        if fetch_full_page and page and page.text:
            body = page.text[:4000]
        elif snippet:
            body = snippet
        blocks.append(f"Source: {title}\nURL: {src.url}\nContent:\n{body}\n")
    text = "\n---\n".join(blocks)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def _chunk_content(msg) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content or "")


def summarize_search_context(
    research_topic: str,
    prior_summary: str | None,
    context: str,
    *,
    on_delta: Callable[[str], None] | None = None,
    iteration: int = 1,
) -> str:
    if not context.strip():
        return prior_summary or ""
    settings = get_settings()
    model = get_chat_model()
    prior = prior_summary.strip() if prior_summary else ""
    user = (
        f"Current date: {current_date_str()}\n"
        f"User topic: {research_topic}\n\n"
        f"Existing summary (may be empty):\n{prior or '(none)'}\n\n"
        f"New search context:\n{context}\n\n"
        "Produce the updated running summary."
    )
    messages = [SystemMessage(content=SUMMARIZER_SYSTEM), HumanMessage(content=user)]

    if settings.enable_summary_streaming and on_delta is not None:
        parts: list[str] = []
        for chunk in model.stream(messages):
            piece = _chunk_content(chunk)
            if not piece:
                continue
            parts.append(piece)
            on_delta(piece)
        content = "".join(parts).strip()
        return content or prior

    msg = model.invoke(messages)
    content = _chunk_content(msg).strip()
    return content or prior
