from __future__ import annotations

from app.agent.prompts import PLANNER_SYSTEM
from app.config import get_settings
from app.llm.ollama_client import get_chat_model, invoke_structured
from app.schemas.research import ResearchPlan


def create_research_plan(question: str) -> ResearchPlan:
    settings = get_settings()
    model = get_chat_model()
    user = (
        f"Research question:\n{question}\n\n"
        f"Maximum research iterations allowed: {settings.effective_max_research_iterations}\n"
        "Provide 3-8 focused research_questions."
    )
    try:
        plan = invoke_structured(model, ResearchPlan, PLANNER_SYSTEM, user)
    except Exception:
        plan = ResearchPlan(
            research_topic=question[:200],
            objective=question,
            research_questions=[question],
            search_strategy="Iterative web search and source extraction",
            expected_output="A cited research report answering the question",
            maximum_research_iterations=settings.effective_max_research_iterations,
        )
    plan.maximum_research_iterations = min(
        plan.maximum_research_iterations,
        settings.effective_max_research_iterations,
    )
    if not plan.research_questions:
        plan.research_questions = [question]
    return plan
