from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.agent.gap_analyzer import analyze_gaps
from app.agent.ldr_reflection import reflect_on_summary
from app.agent.planner import create_research_plan
from app.agent.query_generator import _fallback_queries, generate_search_queries
from app.config import get_settings
from app.database.repository import ResearchRepository
from app.research.information_extractor import extract_findings_from_page, heuristic_findings_from_page
from app.research.report_generator import generate_report_markdown
from app.research.running_summary import format_sources_for_summary, summarize_search_context
from app.schemas.research import GapAnalysis, ResearchStage, SessionStatus
from app.schemas.source import ExtractStatus, SourceRecord, WebPageContent
from app.tools.search_tool import run_web_search
from app.tools.webpage_tool import fetch_webpage

logger = logging.getLogger(__name__)


def _error_message(exc: BaseException) -> str:
    msg = str(exc).strip()
    if msg:
        return msg
    return f"{type(exc).__name__} during research pipeline"


STAGE_LABELS = {
    ResearchStage.UNDERSTANDING: "Understanding research question",
    ResearchStage.PLANNING: "Creating research plan",
    ResearchStage.SEARCHING: "Searching sources",
    ResearchStage.EXTRACTING: "Extracting information",
    ResearchStage.GAP_ANALYSIS: "Identifying research gaps",
    ResearchStage.ADDITIONAL_RESEARCH: "Performing additional research",
    ResearchStage.REPORT: "Generating final report",
}


class ResearchService:
    def __init__(self, repo: ResearchRepository | None = None):
        self.repo = repo or ResearchRepository()
        self.settings = get_settings()

    def _emit(self, session_id: str, stage: ResearchStage, event_type: str = "stage_changed", **payload):
        self.repo.update_session(session_id, stage=stage)
        label = STAGE_LABELS.get(stage, stage.value)
        self.repo.append_event(
            session_id,
            event_type,
            {"stage": stage.value, "label": label, **payload},
        )
        if event_type == "stage_changed":
            self.repo.append_event(
                session_id,
                "activity",
                {"label": label, "detail": payload.get("detail", "")},
            )

    def _run_queries(
        self,
        session_id: str,
        queries: list[str],
    ) -> list[SourceRecord]:
        for q in queries:
            self.repo.append_event(
                session_id,
                "activity",
                {"label": "Searching the web", "detail": q[:120]},
            )
            for item in run_web_search(q):
                src = SourceRecord(
                    session_id=session_id,
                    url=item.url,
                    title=item.title,
                    snippet=item.snippet,
                    published_date=item.published_date,
                    extract_status=ExtractStatus.PENDING,
                )
                src_id = self.repo.upsert_source(src)
                src.id = src_id
        return self.repo.list_sources(session_id)

    def _process_fetched_page(
        self,
        session_id: str,
        src: SourceRecord,
        page: WebPageContent,
    ) -> int:
        if page.fetch_error:
            self.repo.update_source_status(src.id or 0, ExtractStatus.FAILED)
            return 0
        self.repo.update_source_status(src.id or 0, ExtractStatus.SUCCESS)
        if self.settings.effective_skip_llm_page_extract:
            findings = heuristic_findings_from_page(page)
        else:
            findings = extract_findings_from_page(page)
        for f in findings:
            self.repo.add_finding(session_id, src.id, f)
        return 1

    def _extract_sources(
        self,
        session_id: str,
        sources: list[SourceRecord],
    ) -> tuple[int, dict[str, WebPageContent], list[SourceRecord]]:
        limit = self.settings.effective_max_pages_per_iteration
        to_fetch = [s for s in sources if s.extract_status == ExtractStatus.PENDING][:limit]
        pages: dict[str, WebPageContent] = {}
        extracted_count = 0

        if not to_fetch:
            return 0, pages, self.repo.list_sources(session_id)

        self.repo.append_event(
            session_id,
            "activity",
            {"label": "Reading sources", "detail": f"{len(to_fetch)} pages"},
        )

        if len(to_fetch) == 1:
            src = to_fetch[0]
            page = fetch_webpage(src.url)
            pages[src.url] = page
            extracted_count += self._process_fetched_page(session_id, src, page)
        else:
            fetched: list[tuple[SourceRecord, WebPageContent]] = []
            with ThreadPoolExecutor(max_workers=min(len(to_fetch), 4)) as pool:
                future_map = {pool.submit(fetch_webpage, src.url): src for src in to_fetch}
                for future in as_completed(future_map):
                    src = future_map[future]
                    try:
                        page = future.result()
                    except Exception as exc:
                        logger.warning("Fetch failed for %s: %s", src.url, exc)
                        page = WebPageContent(url=src.url, title=src.title or "", text="", fetch_error=str(exc))
                    fetched.append((src, page))
            for src, page in fetched:
                pages[src.url] = page
                extracted_count += self._process_fetched_page(session_id, src, page)

        return extracted_count, pages, self.repo.list_sources(session_id)

    def run(self, session_id: str) -> None:
        detail = self.repo.get_session(session_id)
        if not detail:
            return
        question = detail.question
        self.repo.update_session(session_id, status=SessionStatus.RUNNING)
        gap_notes: list[str] = []
        running_summary = self.repo.get_running_summary(session_id) or ""
        follow_up_query: str | None = None
        gap: GapAnalysis | None = None

        try:
            self._emit(session_id, ResearchStage.UNDERSTANDING)
            self._emit(session_id, ResearchStage.PLANNING)
            plan = create_research_plan(question)
            self.repo.update_session(session_id, plan=plan)

            iteration = 0
            max_iter = min(
                plan.maximum_research_iterations,
                self.settings.effective_max_research_iterations,
            )
            all_findings: list = []
            stop_early = False

            while iteration < max_iter and not stop_early:
                iteration += 1
                self.repo.update_session(session_id, iteration=iteration)
                if iteration > 1:
                    self._emit(session_id, ResearchStage.ADDITIONAL_RESEARCH, iteration=iteration)

                self._emit(session_id, ResearchStage.SEARCHING, iteration=iteration)
                if self.settings.use_ldr_loop and iteration > 1 and follow_up_query:
                    queries = [follow_up_query]
                elif self.settings.use_ldr_loop:
                    queries = generate_search_queries(plan, None)
                else:
                    queries = generate_search_queries(plan, gap if iteration > 1 else None)

                if not queries:
                    queries = _fallback_queries(plan)
                self.repo.add_queries(session_id, iteration, queries)
                self.repo.append_event(
                    session_id,
                    "queries_generated",
                    {"queries": queries, "iteration": iteration},
                )

                sources = self._run_queries(session_id, queries)
                self.repo.append_event(
                    session_id,
                    "search_done",
                    {"sources_discovered": len(sources), "iteration": iteration},
                )

                self._emit(session_id, ResearchStage.EXTRACTING, iteration=iteration)
                extracted_count, pages, sources = self._extract_sources(session_id, sources)
                all_findings = self.repo.list_findings(session_id)
                self.repo.append_event(
                    session_id,
                    "extract_done",
                    {
                        "sources_extracted": extracted_count,
                        "findings_count": len(all_findings),
                        "iteration": iteration,
                    },
                )

                self._emit(session_id, ResearchStage.GAP_ANALYSIS, iteration=iteration)

                if self.settings.use_ldr_loop:
                    iteration_sources = sources[-max(len(queries) * 3, 5) :]
                    context = format_sources_for_summary(
                        iteration_sources,
                        pages,
                        fetch_full_page=self.settings.fetch_full_page,
                    )

                    def on_delta(text: str, *, _iter: int = iteration) -> None:
                        self.repo.append_event(
                            session_id,
                            "summary_delta",
                            {"text": text, "iteration": _iter},
                        )

                    self.repo.append_event(
                        session_id,
                        "activity",
                        {"label": "Writing summary", "detail": f"iteration {iteration}"},
                    )
                    running_summary = summarize_search_context(
                        plan.research_topic,
                        running_summary,
                        context,
                        on_delta=on_delta if self.settings.enable_summary_streaming else None,
                        iteration=iteration,
                    )
                    self.repo.update_running_summary(session_id, running_summary)
                    self.repo.append_event(
                        session_id,
                        "summary_updated",
                        {"chars": len(running_summary), "iteration": iteration},
                    )
                    reflection = reflect_on_summary(plan.research_topic, running_summary, len(all_findings))
                    self.repo.append_event(
                        session_id,
                        "reflection_done",
                        reflection.model_dump(),
                    )
                    if reflection.knowledge_gap:
                        gap_notes.append(reflection.knowledge_gap)
                    follow_up_query = reflection.follow_up_query or None
                    if reflection.sufficient_evidence:
                        stop_early = True
                else:
                    gap = analyze_gaps(plan, all_findings, iteration)
                    self.repo.append_event(session_id, "gap_analysis", gap.model_dump())
                    gap_notes.extend(gap.missing_evidence[:5])
                    gap_notes.extend(gap.unanswered_questions[:5])
                    if gap.sufficient_evidence:
                        stop_early = True

            self._emit(session_id, ResearchStage.REPORT)
            sources = self.repo.list_sources(session_id)
            all_findings = self.repo.list_findings(session_id)
            running_summary = self.repo.get_running_summary(session_id) or running_summary
            report = generate_report_markdown(
                question,
                plan,
                all_findings,
                sources,
                gap_notes=gap_notes,
                iteration_count=iteration,
                running_summary=running_summary or None,
            )
            report_path = self.settings.reports_dir / f"{session_id}.md"
            report_path.write_text(report, encoding="utf-8")
            self.repo.update_session(
                session_id,
                status=SessionStatus.COMPLETE,
                stage=ResearchStage.COMPLETE,
                report_md=report,
            )
            self.repo.append_event(session_id, "report_ready", {"report_path": str(report_path)})
        except Exception as exc:
            logger.exception("Research session failed")
            self.repo.update_session(
                session_id,
                status=SessionStatus.FAILED,
                stage=ResearchStage.FAILED,
                error=_error_message(exc),
            )
            self.repo.append_event(
                session_id,
                "failed",
                {"error": _error_message(exc), "trace": traceback.format_exc()[-2000:]},
            )
