from app.research.running_summary import format_sources_for_summary
from app.schemas.source import ExtractStatus, SourceRecord, WebPageContent


def test_format_sources_truncates_and_dedupes():
    sources = [
        SourceRecord(session_id="s", url="https://a.com", title="A", snippet="x" * 1000, extract_status=ExtractStatus.PENDING),
        SourceRecord(session_id="s", url="https://a.com/", title="A dup", snippet="y", extract_status=ExtractStatus.PENDING),
    ]
    text = format_sources_for_summary(sources, {}, fetch_full_page=False, max_chars=500)
    assert len(text) <= 503
    assert "https://a.com" in text


def test_summarize_extends_prior():
    from unittest.mock import MagicMock, patch

    from app.research.running_summary import summarize_search_context

    model = MagicMock()
    model.invoke.return_value = MagicMock(content="Updated summary paragraph.")
    with patch("app.research.running_summary.get_chat_model", return_value=model):
        out = summarize_search_context("topic", "Old summary", "New context from web")
    assert "Updated summary" in out


def test_summarize_streams_with_callback():
    from unittest.mock import MagicMock, patch

    from app.research.running_summary import summarize_search_context

    model = MagicMock()
    model.stream.return_value = [
        MagicMock(content="Hello "),
        MagicMock(content="world."),
    ]
    deltas: list[str] = []

    with patch("app.research.running_summary.get_chat_model", return_value=model):
        out = summarize_search_context(
            "topic",
            "",
            "context",
            on_delta=deltas.append,
        )
    assert out == "Hello world."
    assert deltas == ["Hello ", "world."]
    model.stream.assert_called_once()
    model.invoke.assert_not_called()
