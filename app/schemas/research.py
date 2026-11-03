from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResearchStage(str, Enum):
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    SEARCHING = "searching"
    EXTRACTING = "extracting"
    GAP_ANALYSIS = "gap_analysis"
    ADDITIONAL_RESEARCH = "additional_research"
    REPORT = "report"
    COMPLETE = "complete"
    FAILED = "failed"


class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class ResearchPlan(BaseModel):
    research_topic: str
    objective: str
    research_questions: list[str] = Field(default_factory=list, min_length=1)
    search_strategy: str = ""
    expected_output: str = ""
    maximum_research_iterations: int = Field(default=2, ge=1, le=10)


class SearchQueryBatch(BaseModel):
    queries: list[str] = Field(default_factory=list, min_length=1)


class GapAnalysis(BaseModel):
    sufficient_evidence: bool = False
    unanswered_questions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    conflicting_findings: list[str] = Field(default_factory=list)
    outdated_sources: list[str] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list)
    rationale: str = ""


class ReflectionResult(BaseModel):
    knowledge_gap: str = ""
    follow_up_query: str = ""
    sufficient_evidence: bool = False


class ResearchSessionSummary(BaseModel):
    id: str
    question: str
    status: SessionStatus
    stage: ResearchStage
    iteration: int
    sources_discovered: int = 0
    sources_extracted: int = 0
    findings_count: int = 0
    error: str | None = None
    created_at: str
    updated_at: str


class ResearchSessionDetail(ResearchSessionSummary):
    plan: ResearchPlan | None = None
    search_queries: list[str] = Field(default_factory=list)
    report_markdown: str | None = None
    running_summary_md: str | None = None


class StartResearchRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)


class StartResearchResponse(BaseModel):
    session_id: str
    status: SessionStatus


class ResearchEvent(BaseModel):
    seq: int
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str
