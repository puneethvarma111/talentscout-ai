from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceItem(BaseModel):
    index: int
    title: str
    url: str


class CitationValidationResult(BaseModel):
    valid: bool
    report_markdown: str
    references: list[ReferenceItem] = Field(default_factory=list)
    removed_citations: list[int] = Field(default_factory=list)
    flagged_claims: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    markdown: str
    references: list[ReferenceItem] = Field(default_factory=list)
    validation: CitationValidationResult | None = None
