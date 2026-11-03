from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ExtractStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SearchResultItem(BaseModel):
    title: str = ""
    url: str
    snippet: str = ""
    published_date: str | None = None


class WebPageContent(BaseModel):
    url: str
    title: str = ""
    headings: list[str] = Field(default_factory=list)
    paragraphs: list[str] = Field(default_factory=list)
    text: str = ""
    fetch_error: str | None = None


class EvidenceQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExtractedFinding(BaseModel):
    main_finding: str
    important_facts: list[str] = Field(default_factory=list)
    technical_details: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    relevant_dates: list[str] = Field(default_factory=list)
    source_url: str
    evidence_quote: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_quality: EvidenceQuality = EvidenceQuality.MEDIUM


class SourceRecord(BaseModel):
    id: int | None = None
    session_id: str
    url: str
    title: str = ""
    snippet: str = ""
    extract_status: ExtractStatus = ExtractStatus.PENDING
    published_date: str | None = None
