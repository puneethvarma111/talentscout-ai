from unittest.mock import patch

from app.config import get_settings
from app.database.connection import init_db
from app.database.repository import ResearchRepository
from app.research.research_service import ResearchService
from app.schemas.research import GapAnalysis, ReflectionResult, ResearchPlan, SessionStatus
from app.schemas.source import ExtractedFinding, SearchResultItem, WebPageContent


def test_research_service_ldr_loop(tmp_path, monkeypatch):
    db = tmp_path / "test.sqlite3"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    monkeypatch.setenv("USE_LDR_LOOP", "true")
    get_settings.cache_clear()
    init_db(db)
    repo = ResearchRepository()
    session_id = repo.create_session("Test LDR")

    plan = ResearchPlan(
        research_topic="T",
        objective="O",
        research_questions=["Q1"],
        maximum_research_iterations=2,
    )
    reflection = ReflectionResult(
        knowledge_gap="need more",
        follow_up_query="follow up",
        sufficient_evidence=True,
    )

    with patch("app.research.research_service.create_research_plan", return_value=plan), patch(
        "app.research.research_service.generate_search_queries", return_value=["q1"]
    ), patch(
        "app.research.research_service.run_web_search",
        return_value=[SearchResultItem(title="T", url="https://example.com/p", snippet="s")],
    ), patch(
        "app.research.research_service.fetch_webpage",
        return_value=WebPageContent(url="https://example.com/p", title="T", text="fact " * 50),
    ), patch(
        "app.research.research_service.extract_findings_from_page",
        return_value=[ExtractedFinding(main_finding="fact", source_url="https://example.com/p")],
    ), patch("app.research.research_service.summarize_search_context", return_value="Running sum"), patch(
        "app.research.research_service.reflect_on_summary", return_value=reflection
    ):
        ResearchService(repo).run(session_id)

    detail = repo.get_session(session_id)
    assert detail.status == SessionStatus.COMPLETE
    assert detail.running_summary_md == "Running sum"


def test_research_service_runs_iteration_with_mocks(tmp_path, monkeypatch):
    db = tmp_path / "test.sqlite3"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    monkeypatch.setenv("USE_LDR_LOOP", "false")
    get_settings.cache_clear()
    init_db(db)
    repo = ResearchRepository()
    session_id = repo.create_session("Test question")

    plan = ResearchPlan(
        research_topic="T",
        objective="O",
        research_questions=["Q1"],
        maximum_research_iterations=2,
    )
    gap1 = GapAnalysis(sufficient_evidence=False, follow_up_queries=["follow up query"])
    gap2 = GapAnalysis(sufficient_evidence=True)

    with patch("app.research.research_service.create_research_plan", return_value=plan), patch(
        "app.research.research_service.generate_search_queries", return_value=["query one"]
    ), patch(
        "app.research.research_service.run_web_search",
        return_value=[SearchResultItem(title="T", url="https://example.com/p", snippet="s")],
    ), patch(
        "app.research.research_service.fetch_webpage",
        return_value=WebPageContent(url="https://example.com/p", title="T", text="fact " * 50),
    ), patch(
        "app.research.research_service.extract_findings_from_page",
        return_value=[
            ExtractedFinding(main_finding="A fact", source_url="https://example.com/p"),
        ],
    ), patch(
        "app.research.research_service.analyze_gaps", side_effect=[gap1, gap2]
    ):
        ResearchService(repo).run(session_id)

    detail = repo.get_session(session_id)
    assert detail.status == SessionStatus.COMPLETE
    assert detail.report_markdown
    assert detail.iteration >= 1
