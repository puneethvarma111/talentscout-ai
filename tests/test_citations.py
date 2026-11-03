from app.schemas.source import ExtractStatus, SourceRecord
from app.tools.citation_tool import validate_citations


def test_citation_validation_removes_invalid_markers():
    sources = [
        SourceRecord(session_id="s", url="https://a.com", title="A", extract_status=ExtractStatus.SUCCESS),
    ]
    report = "Claim one [1]. Claim fake [99]."
    result = validate_citations(report, sources)
    assert "[99]" not in result.report_markdown
    assert 99 in result.removed_citations


def test_reference_urls_must_match_session():
    sources = [
        SourceRecord(session_id="s", url="https://a.com", title="A", extract_status=ExtractStatus.SUCCESS),
    ]
    report = "See https://evil.com/x [1]"
    result = validate_citations(report, sources)
    assert any("evil.com" in w or "evil.com" in f for w in result.warnings for f in result.flagged_claims) or result.warnings
