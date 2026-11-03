from __future__ import annotations

from app.schemas.report import ReferenceItem
from app.schemas.research import ResearchPlan
from app.schemas.source import ExtractedFinding, SourceRecord
from app.tools.citation_tool import validate_citations


def _group_findings(findings: list[ExtractedFinding]) -> dict[str, list[ExtractedFinding]]:
    grouped: dict[str, list[ExtractedFinding]] = {}
    for f in findings:
        grouped.setdefault(f.source_url, []).append(f)
    return grouped


def generate_report_markdown(
    question: str,
    plan: ResearchPlan,
    findings: list[ExtractedFinding],
    sources: list[SourceRecord],
    gap_notes: list[str],
    iteration_count: int,
    running_summary: str | None = None,
) -> str:
    successful = [s for s in sources if s.extract_status.value == "success"]
    url_to_index = {s.url: i + 1 for i, s in enumerate(successful)}
    grouped = _group_findings(findings)

    lines: list[str] = [
        "# Research Report",
        "",
        "## 1. Executive Summary",
        "",
    ]
    if running_summary and running_summary.strip():
        lines.append(running_summary.strip())
        lines.append("")
        lines.append("_Note: Summary synthesized across search iterations; cited claims appear in Key Findings._")
    elif findings:
        top = findings[:5]
        for f in top:
            cite = url_to_index.get(f.source_url)
            suffix = f" [{cite}]" if cite else ""
            lines.append(f"- {f.main_finding}{suffix}")
    else:
        lines.append("- Insufficient extracted evidence to summarize the topic confidently.")

    lines.extend(
        [
            "",
            "## 2. Research Objective",
            "",
            plan.objective or question,
            "",
            "## 3. Research Methodology",
            "",
            f"- Iterations completed: {iteration_count}",
            f"- Sources discovered: {len(sources)}",
            f"- Sources successfully extracted: {len(successful)}",
            f"- Findings recorded: {len(findings)}",
            "- Web search via DuckDuckGo; page text extracted with httpx and BeautifulSoup.",
            "- Iterative summarize/reflect loop adapted from langchain-ai/local-deep-researcher (MIT).",
            "",
            "## 4. Key Findings",
            "",
        ]
    )
    for f in findings[:25]:
        cite = url_to_index.get(f.source_url)
        suffix = f" [{cite}]" if cite else ""
        lines.append(f"- {f.main_finding}{suffix}")
        for fact in f.important_facts[:3]:
            lines.append(f"  - {fact}")
    lines.extend(["", "## 5. Detailed Analysis", ""])
    for url, items in list(grouped.items())[:12]:
        idx = url_to_index.get(url)
        header = f"### Source [{idx}]" if idx else "### Source"
        lines.append(header)
        for item in items[:3]:
            lines.append(item.main_finding)
            if item.evidence_quote:
                lines.append(f"> {item.evidence_quote[:400]}")
        lines.append("")

    lines.extend(["## 6. Comparison and Evaluation", ""])
    compare = [f for f in findings if any(k in f.main_finding.lower() for k in ("compare", "versus", "vs", "strength", "weakness"))]
    if compare:
        for f in compare[:10]:
            cite = url_to_index.get(f.source_url)
            lines.append(f"- {f.main_finding}" + (f" [{cite}]" if cite else ""))
    else:
        lines.append("- Comparative conclusions are limited to synthesized analysis of collected findings.")

    lines.extend(["", "## 7. Gaps and Limitations", ""])
    for note in gap_notes:
        lines.append(f"- {note}")
    if not findings:
        lines.append("- No verified findings were extracted from web sources in this session.")
    lines.extend(["", "## 8. Recommendations", ""])
    lines.append(
        "- Treat recommendations as analyst judgment based on cited findings; verify critical decisions against primary sources."
    )
    lines.extend(["", "## 9. Conclusion", ""])
    lines.append(plan.expected_output or f"Research on: {plan.research_topic}")
    lines.extend(["", "## 10. References", ""])
    for i, src in enumerate(successful, start=1):
        title = src.title or src.url
        lines.append(f"[{i}] {title} — {src.url}")

    draft = "\n".join(lines)
    validation = validate_citations(draft, successful)
    if validation.warnings:
        draft += "\n\n### Evidence notes\n"
        for w in validation.warnings[:10]:
            draft += f"- {w}\n"
    return validation.report_markdown
