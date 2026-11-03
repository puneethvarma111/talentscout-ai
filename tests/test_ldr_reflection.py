from unittest.mock import MagicMock, patch

from app.agent.ldr_reflection import reflect_on_summary
from app.schemas.research import ReflectionResult


def test_reflect_on_summary_mock():
    mock = ReflectionResult(
        knowledge_gap="Missing benchmarks",
        follow_up_query="AI agent framework benchmarks 2025",
        sufficient_evidence=False,
    )
    with patch("app.agent.ldr_reflection.invoke_structured", return_value=mock):
        with patch("app.agent.ldr_reflection.get_chat_model", return_value=MagicMock()):
            result = reflect_on_summary("AI agents", "Some summary text.", findings_count=1)
    assert result.follow_up_query == "AI agent framework benchmarks 2025"
