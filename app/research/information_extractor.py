from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent.prompts import EXTRACT_SYSTEM
from app.config import get_settings
from app.llm.ollama_client import get_chat_model, invoke_structured
from app.schemas.source import EvidenceQuality, ExtractedFinding, WebPageContent


class FindingBatch(BaseModel):
    findings: list[ExtractedFinding] = Field(default_factory=list)


def heuristic_findings_from_page(page: WebPageContent) -> list[ExtractedFinding]:
    """Non-LLM fallback: one coarse finding from page text or snippet."""
    if page.fetch_error:
        return []
    text = (page.text or "").strip()
    if not text and page.paragraphs:
        text = page.paragraphs[0]
    if not text:
        return []
    return [
        ExtractedFinding(
            main_finding=text[:500],
            source_url=page.url,
            evidence_quote=(page.paragraphs[0][:300] if page.paragraphs else text[:300]),
            confidence=0.4,
            evidence_quality=EvidenceQuality.LOW,
        )
    ]


def extract_findings_from_page(page: WebPageContent) -> list[ExtractedFinding]:
    if page.fetch_error or not page.text:
        return []
    settings = get_settings()
    max_chars = 6000 if settings.is_fast_mode else 12000
    model = get_chat_model()
    user = (
        f"Source URL (for output fields): {page.url}\n"
        f"Title: {page.title}\n\n"
        "=== UNTRUSTED WEBPAGE CONTENT START ===\n"
        f"{page.text[:max_chars]}\n"
        "=== UNTRUSTED WEBPAGE CONTENT END ===\n\n"
        "Extract 1-5 findings grounded in the content. Set source_url to the source URL above."
    )
    try:
        batch = invoke_structured(model, FindingBatch, EXTRACT_SYSTEM, user)
    except Exception:
        return []
    cleaned: list[ExtractedFinding] = []
    for f in batch.findings:
        if page.url not in f.source_url and f.source_url != page.url:
            f = f.model_copy(update={"source_url": page.url})
        if not f.main_finding.strip():
            continue
        cleaned.append(f)
    if not cleaned and page.text:
        cleaned = heuristic_findings_from_page(page)
    return cleaned
