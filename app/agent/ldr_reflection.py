from __future__ import annotations

from app.agent.ldr_prompts import REFLECTION_SYSTEM
from app.agent.query_generator import _fallback_queries
from app.llm.ollama_client import get_chat_model, invoke_structured
from app.schemas.research import ReflectionResult, ResearchPlan


class ReflectionOutput(ReflectionResult):
    pass


def reflect_on_summary(research_topic: str, running_summary: str, findings_count: int) -> ReflectionResult:
    model = get_chat_model()
    user = (
        f"Research topic: {research_topic}\n\n"
        f"Findings extracted so far: {findings_count}\n\n"
        f"Running summary:\n{running_summary[:12000]}\n\n"
        "Return knowledge_gap, follow_up_query, and sufficient_evidence (true if summary adequately covers the topic)."
    )
    try:
        result = invoke_structured(model, ReflectionOutput, REFLECTION_SYSTEM, user)
        if not result.follow_up_query.strip() and not result.sufficient_evidence:
            plan = ResearchPlan(
                research_topic=research_topic,
                objective=research_topic,
                research_questions=[research_topic],
            )
            fb = _fallback_queries(plan)
            result = result.model_copy(update={"follow_up_query": fb[0] if fb else research_topic})
        return result
    except Exception:
        sufficient = findings_count >= 3 and len(running_summary) > 400
        plan = ResearchPlan(
            research_topic=research_topic,
            objective=research_topic,
            research_questions=[research_topic],
        )
        fb = _fallback_queries(plan)
        return ReflectionResult(
            knowledge_gap="Unable to parse reflection; continuing search.",
            follow_up_query=fb[0] if fb else research_topic,
            sufficient_evidence=sufficient,
        )
