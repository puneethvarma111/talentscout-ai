import pytest

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_fast_mode_effective_limits(monkeypatch):
    monkeypatch.setenv("RESEARCH_MODE", "fast")
    monkeypatch.setenv("MAX_RESEARCH_ITERATIONS", "3")
    monkeypatch.setenv("MAX_PAGES_PER_ITERATION", "5")
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "8")
    get_settings.cache_clear()
    s = Settings()
    assert s.effective_max_research_iterations == 1
    assert s.effective_max_pages_per_iteration == 2
    assert s.effective_max_search_results == 5
    assert s.effective_skip_llm_page_extract is True
    assert s.effective_structured_output_retries == 1
    assert s.effective_ollama_num_ctx == 4096
    assert s.effective_ollama_num_predict == 512
    assert s.effective_summary_context_max_chars == 8000


def test_skip_llm_page_extract_env_override(monkeypatch):
    monkeypatch.setenv("RESEARCH_MODE", "balanced")
    monkeypatch.setenv("SKIP_LLM_PAGE_EXTRACT", "true")
    get_settings.cache_clear()
    s = Settings()
    assert s.effective_skip_llm_page_extract is True


def test_balanced_mode_defaults(monkeypatch):
    monkeypatch.delenv("RESEARCH_MODE", raising=False)
    get_settings.cache_clear()
    s = Settings()
    assert s.research_mode == "balanced"
    assert s.effective_skip_llm_page_extract is False
    assert s.effective_max_research_iterations == 3
