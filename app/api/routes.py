from __future__ import annotations

import asyncio
import json
import threading
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.api.dependencies import get_repo, get_settings_dep
from app.config import Settings
from app.database.repository import ResearchRepository
from app.llm.ollama_client import check_ollama_health
from app.research.pdf_export import markdown_to_pdf_bytes
from app.research.research_service import ResearchService
from app.schemas.research import (
    ResearchSessionDetail,
    ResearchSessionSummary,
    StartResearchRequest,
    StartResearchResponse,
)

router = APIRouter(prefix="/api")


def _run_research(session_id: str) -> None:
    try:
        ResearchService().run(session_id)
    except Exception:
        # errors are persisted on the session row
        pass


def _start_research_thread(session_id: str) -> None:
    thread = threading.Thread(
        target=_run_research,
        args=(session_id,),
        daemon=True,
        name=f"research-{session_id[:8]}",
    )
    thread.start()


@router.get("/health")
def health():
    ollama = check_ollama_health()
    return {
        "ok": True,
        "app": "local-research-ai",
        "ollama_ok": ollama.get("ok", False),
        "ollama": ollama,
    }


@router.post("/research", response_model=StartResearchResponse)
def start_research(
    body: StartResearchRequest,
    settings: Settings = Depends(get_settings_dep),
    repo: ResearchRepository = Depends(get_repo),
):
    q = body.question.strip()
    if len(q) > settings.max_question_length:
        raise HTTPException(status_code=400, detail="Question too long")
    from app.schemas.research import SessionStatus

    session_id = repo.create_session(q)
    repo.update_session(session_id, status=SessionStatus.RUNNING)
    _start_research_thread(session_id)
    return StartResearchResponse(session_id=session_id, status=SessionStatus.RUNNING)


@router.get("/research/history", response_model=list[ResearchSessionSummary])
def list_history(repo: ResearchRepository = Depends(get_repo)):
    return repo.list_history()


@router.get("/research/{session_id}", response_model=ResearchSessionDetail)
def get_session(session_id: str, repo: ResearchRepository = Depends(get_repo)):
    detail = repo.get_session(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.get("/research/{session_id}/report")
def get_report(session_id: str, repo: ResearchRepository = Depends(get_repo)):
    detail = repo.get_session(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    if not detail.report_markdown:
        raise HTTPException(status_code=404, detail="Report not ready")
    sources = repo.list_sources(session_id)
    refs = [{"title": s.title or s.url, "url": s.url} for s in sources if s.extract_status.value == "success"]
    return {"markdown": detail.report_markdown, "references": refs}


@router.get("/research/{session_id}/report.pdf")
def get_report_pdf(session_id: str, repo: ResearchRepository = Depends(get_repo)):
    detail = repo.get_session(session_id)
    if not detail or not detail.report_markdown:
        raise HTTPException(status_code=404, detail="Report not ready")
    pdf = markdown_to_pdf_bytes(detail.report_markdown)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="research-{session_id[:8]}.pdf"'},
    )


@router.get("/research/{session_id}/events/poll")
def poll_events(session_id: str, since_seq: int = 0, repo: ResearchRepository = Depends(get_repo)):
    if not repo.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return repo.list_events(session_id, since_seq=since_seq)


@router.get("/research/{session_id}/events")
async def stream_events(
    session_id: str,
    since_seq: int = 0,
    repo: ResearchRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings_dep),
):
    if not repo.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator() -> AsyncIterator[str]:
        last = since_seq
        while True:
            events = repo.list_events(session_id, since_seq=last)
            for ev in events:
                last = ev["seq"]
                yield f"data: {json.dumps(ev)}\n\n"
            detail = repo.get_session(session_id)
            if detail and detail.status.value in ("complete", "failed"):
                yield f"data: {json.dumps({'type': 'stream_end', 'status': detail.status.value})}\n\n"
                break
            await asyncio.sleep(settings.sse_poll_interval_sec)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/research/{session_id}")
def delete_session(session_id: str, repo: ResearchRepository = Depends(get_repo)):
    if not repo.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}
