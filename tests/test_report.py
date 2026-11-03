from app.research.report_generator import generate_report_markdown
from app.schemas.research import ResearchPlan
from app.schemas.source import EvidenceQuality, ExtractedFinding, ExtractStatus, SourceRecord


def test_report_contains_required_sections():
    plan = ResearchPlan(
        research_topic="Agents",
        objective="Compare agent frameworks",
        research_questions=["Which are open source?"],
    )
    findings = [
        ExtractedFinding(
            main_finding="LangChain provides composable agent primitives.",
            source_url="https://example.com/lc",
            evidence_quality=EvidenceQuality.HIGH,
        )
    ]
    sources = [
        SourceRecord(
            session_id="x",
            url="https://example.com/lc",
            title="LangChain",
            extract_status=ExtractStatus.SUCCESS,
        )
    ]
    md = generate_report_markdown("Q", plan, findings, sources, gap_notes=["Limited sources"], iteration_count=1)
    for section in [
        "## 1. Executive Summary",
        "## 10. References",
        "LangChain provides composable",
    ]:
        assert section in md


def test_report_uses_running_summary():
    plan = ResearchPlan(
        research_topic="Agents",
        objective="Compare",
        research_questions=["Q"],
    )
    md = generate_report_markdown(
        "Q",
        plan,
        [],
        [],
        gap_notes=[],
        iteration_count=1,
        running_summary="IterDRAG running summary text.",
    )
    assert "IterDRAG running summary text." in md
