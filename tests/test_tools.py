from unittest.mock import patch

import httpx
import respx

from app.research.url_safety import URLSafetyError, validate_public_http_url
from app.tools.search_tool import DuckDuckGoSearchProvider, dedupe_search_results, run_web_search
from app.tools.webpage_tool import fetch_webpage
from app.schemas.source import SearchResultItem


def test_dedupe_search_results():
    items = [
        SearchResultItem(title="A", url="https://example.com/a", snippet="x"),
        SearchResultItem(title="B", url="https://example.com/a/", snippet="y"),
    ]
    assert len(dedupe_search_results(items)) == 1


def test_ssrf_blocks_localhost():
    try:
        validate_public_http_url("http://127.0.0.1/secret")
        assert False, "expected error"
    except URLSafetyError:
        pass


@respx.mock
def test_fetch_webpage_extracts_text():
    html = "<html><body><main><p>" + ("Hello world. " * 20) + "</p></main></body></html>"
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(200, text=html, headers={"content-type": "text/html; charset=utf-8"})
    )
    page = fetch_webpage("https://example.com/article")
    assert page.fetch_error is None
    assert "Hello world" in page.text


def test_run_web_search_mock_provider():
    class FakeProvider:
        def search(self, query: str, max_results: int):
            return [SearchResultItem(title="T", url="https://a.com", snippet="s")]

    results = run_web_search("test", provider=FakeProvider())
    assert len(results) == 1
