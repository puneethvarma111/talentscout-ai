from __future__ import annotations

import logging
from typing import Protocol

from ddgs import DDGS

from app.config import get_settings
from app.schemas.source import SearchResultItem

logger = logging.getLogger(__name__)


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int) -> list[SearchResultItem]: ...


class DuckDuckGoSearchProvider:
    def search(self, query: str, max_results: int) -> list[SearchResultItem]:
        try:
            rows = DDGS().text(query, max_results=max_results)
        except Exception as exc:
            logger.warning("Search failed for %r: %s", query, exc)
            return []
        results: list[SearchResultItem] = []
        for row in rows:
            url = row.get("href") or row.get("url") or ""
            if not url:
                continue
            results.append(
                SearchResultItem(
                    title=row.get("title") or "",
                    url=url,
                    snippet=row.get("body") or row.get("snippet") or "",
                    published_date=row.get("date"),
                )
            )
        return results


def dedupe_search_results(items: list[SearchResultItem]) -> list[SearchResultItem]:
    seen: set[str] = set()
    out: list[SearchResultItem] = []
    for item in items:
        key = item.url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def run_web_search(query: str, max_results: int | None = None, provider: SearchProvider | None = None) -> list[SearchResultItem]:
    settings = get_settings()
    limit = max_results or settings.effective_max_search_results
    provider = provider or DuckDuckGoSearchProvider()
    return dedupe_search_results(provider.search(query, min(max(limit, 1), 15)))
