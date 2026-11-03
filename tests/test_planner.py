from unittest.mock import MagicMock, patch

from app.agent.planner import create_research_plan
from app.schemas.research import ResearchPlan


def test_create_research_plan_parses_mock_llm():
    mock_plan = ResearchPlan(
        research_topic="AI agents",
        objective="Compare frameworks",
        research_questions=["What frameworks exist?", "Which support local LLMs?"],
        search_strategy="web search",
        expected_output="Recommendation",
        maximum_research_iterations=2,
    )
    mock_model = MagicMock()
    with patch("app.agent.planner.invoke_structured", return_value=mock_plan):
        with patch("app.agent.planner.get_chat_model", return_value=mock_model):
            plan = create_research_plan("Compare AI agent frameworks")
    assert plan.research_topic == "AI agents"
    assert len(plan.research_questions) >= 2
