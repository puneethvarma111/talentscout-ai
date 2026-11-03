from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent.prompts import GAP_SYSTEM
from app.llm.ollama_client import get_chat_model, invoke_structured
from app.schemas.research import GapAnalysis, ResearchPlan
from app.schemas.source import ExtractedFinding


class GapAnalysisInput(BaseModel):
    sufficient_evidence: bool = False
    unanswered_questions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    conflicting_findings: list[str] = Field(default_factory=list)
    outdated_sources: list[str] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list)
    rationale: str = ""


def analyze_gaps(plan: ResearchPlan, findings: list[ExtractedFinding], iteration: int) -> GapAnalysis:
    model = get_chat_model()
    findings_text = "\n".join(
        f"- [{f.source_url}] {f.main_finding} | facts: {', '.join(f.important_facts[:3])}"
        for f in findings[:40]
    ) or "(no findings yet)"
    user = (
        f"Iteration: {iteration}\n"
        f"Research questions:\n" + "\n".join(f"- {q}" for q in plan.research_questions) + "\n\n"
        f"Findings:\n{findings_text}\n\n"
        "Decide if evidence is sufficient to write the report. If not, provide follow_up_queries."
    )
    try:
        result = invoke_structured(model, GapAnalysisInput, GAP_SYSTEM, user)
        return GapAnalysis.model_validate(result.model_dump())
    except Exception:
        sufficient = len(findings) >= max(3, len(plan.research_questions))
        return GapAnalysis(
            sufficient_evidence=sufficient,
            unanswered_questions=[] if sufficient else plan.research_questions,
            missing_evidence=[] if sufficient else ["Need more primary web sources"],
            follow_up_queries=[] if sufficient else _fallback_followups(plan, iteration),
            rationale="Fallback gap analysis (model output unavailable).",
        )


def _fallback_followups(plan: ResearchPlan, iteration: int) -> list[str]:
    base = [plan.research_topic, *plan.research_questions[:2]]
    return [f"{q} evidence {iteration}" for q in base if q][:3]
