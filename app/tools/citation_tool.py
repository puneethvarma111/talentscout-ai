from __future__ import annotations

import re

from langchain_core.tools import tool

from app.schemas.report import CitationValidationResult, ReferenceItem
from app.schemas.source import SourceRecord


def build_reference_list(sources: list[SourceRecord]) -> list[ReferenceItem]:
    refs: list[ReferenceItem] = []
    for idx, src in enumerate(sources, start=1):
        if src.extract_status.value != "success":
            continue
        refs.append(ReferenceItem(index=idx, title=src.title or src.url, url=src.url))
    return refs


def validate_citations(report_md: str, sources: list[SourceRecord]) -> CitationValidationResult:
    url_set = {s.url for s in sources}
    refs = build_reference_list(sources)
    valid_indices = {r.index for r in refs}
    removed: list[int] = []
    flagged: list[str] = []
    warnings: list[str] = []

    def replacer(match: re.Match[str]) -> str:
        num = int(match.group(1))
        if num not in valid_indices:
            removed.append(num)
            return ""
        return match.group(0)

    cleaned = re.sub(r"\[(\d+)\]", replacer, report_md)
    cleaned = re.sub(r"\[\s*\]", "", cleaned)

    for line in report_md.splitlines():
        if line.strip().startswith("http") and line.strip() not in url_set:
            flagged.append(line.strip()[:200])

    ref_urls_in_report = set(re.findall(r"https?://[^\s\)>]+", cleaned))
    for u in ref_urls_in_report:
        if u.rstrip(".,)") not in url_set:
            warnings.append(f"Report mentions URL not in session sources: {u[:120]}")

    if removed:
        warnings.append(f"Removed invalid citation markers: {sorted(set(removed))}")

    return CitationValidationResult(
        valid=len(removed) == 0 and not flagged,
        report_markdown=cleaned,
        references=refs,
        removed_citations=sorted(set(removed)),
        flagged_claims=flagged,
        warnings=warnings,
    )


@tool
def validate_report_citations(report_markdown: str, source_urls: list[str]) -> str:
    """Validate inline citations against known source URLs."""
    from app.schemas.source import ExtractStatus, SourceRecord

    sources = [
        SourceRecord(session_id="x", url=u, title=u, extract_status=ExtractStatus.SUCCESS)
        for u in source_urls
    ]
    result = validate_citations(report_markdown, sources)
    return result.model_dump_json()
