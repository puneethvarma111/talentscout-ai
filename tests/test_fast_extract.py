from unittest.mock import MagicMock, patch

from app.research.research_service import ResearchService
from app.database.connection import init_db
from app.database.repository import ResearchRepository
from app.config import get_settings
from app.schemas.research import ReflectionResult, ResearchPlan, SessionStatus
from app.schemas.source import SearchResultItem, WebPageContent


def test_fast_mode_skips_llm_page_extract(tmp_path, monkeypatch):
    db = tmp_path / "test.sqlite3"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    monkeypatch.setenv("RESEARCH_MODE", "fast")
    monkeypatch.setenv("USE_LDR_LOOP", "true")
    get_settings.cache_clear()
    init_db(db)
    repo = ResearchRepository()
    session_id = repo.create_session("Fast test")

    plan = ResearchPlan(
        research_topic="T",
        objective="O",
        research_questions=["Q1"],
        maximum_research_iterations=1,
    )
    reflection = ReflectionResult(sufficient_evidence=True)

    with patch("app.research.research_service.create_research_plan", return_value=plan), patch(
        "app.research.research_service.generate_search_queries", return_value=["q1"]
    ), patch(
        "app.research.research_service.run_web_search",
        return_value=[SearchResultItem(title="T", url="https://example.com/p", snippet="s")],
    ), patch(
        "app.research.research_service.fetch_webpage",
        return_value=WebPageContent(url="https://example.com/p", title="T", text="fact " * 50),
    ), patch("app.research.research_service.extract_findings_from_page") as mock_llm_extract, patch(
        "app.research.research_service.heuristic_findings_from_page",
        return_value=[],
    ) as mock_heuristic, patch(
        "app.research.research_service.summarize_search_context", return_value="Sum"
    ), patch(
        "app.research.research_service.reflect_on_summary", return_value=reflection
    ):
        ResearchService(repo).run(session_id)

    mock_llm_extract.assert_not_called()
    mock_heuristic.assert_called()
    assert repo.get_session(session_id).status == SessionStatus.COMPLETE
