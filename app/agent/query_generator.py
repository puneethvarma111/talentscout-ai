from __future__ import annotations

from app.agent.prompts import QUERY_SYSTEM
from app.config import get_settings
from app.llm.ollama_client import get_chat_model, invoke_structured
from app.schemas.research import GapAnalysis, ResearchPlan, SearchQueryBatch


def _normalize(q: str) -> str:
    return " ".join(q.lower().split())


def dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = _normalize(q)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(q.strip())
    return out


def _fallback_queries(plan: ResearchPlan) -> list[str]:
    seeds = [plan.research_topic, plan.objective, *plan.research_questions]
    seeds.extend(f"{plan.research_topic} {q}" for q in plan.research_questions[:2])
    return dedupe_queries([s for s in seeds if s and s.strip()])[:6]


def generate_search_queries(plan: ResearchPlan, gap: GapAnalysis | None = None) -> list[str]:
    settings = get_settings()
    model = get_chat_model()
    gap_text = ""
    if gap and gap.follow_up_queries:
        gap_text = "Prioritize these follow-up queries:\n" + "\n".join(f"- {q}" for q in gap.follow_up_queries)
    query_instruction = "Generate 2-3 search queries." if settings.is_fast_mode else "Generate 4-6 search queries."
    user = (
        f"Topic: {plan.research_topic}\nObjective: {plan.objective}\n"
        f"Research questions:\n" + "\n".join(f"- {q}" for q in plan.research_questions) + "\n"
        f"{gap_text}\n{query_instruction}"
    )
    cap = 3 if settings.is_fast_mode else 8
    combined: list[str] = []
    try:
        batch = invoke_structured(model, SearchQueryBatch, QUERY_SYSTEM, user)
        combined = dedupe_queries(list(batch.queries))
    except Exception:
        combined = []
    if gap and gap.follow_up_queries:
        combined = dedupe_queries(list(gap.follow_up_queries) + combined)
    if not combined:
        combined = _fallback_queries(plan)
    return combined[:cap]
