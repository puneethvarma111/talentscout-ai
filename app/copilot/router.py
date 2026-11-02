from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.copilot import agent, hrms, llm
from app.copilot.docs import extract_text, make_doc
from app.copilot.tools import get_session

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class ChatIn(BaseModel):
    message: str
    session_id: str
    persona: str = "employee"


class Decision(BaseModel):
    session_id: str
    decision: str  # approve | reject
    content: str | None = None


@router.get("/config")
def config():
    p = llm.provider_name()
    return {"provider": p, "model": llm.model_name(p), "mock": p == "mock", "data_source": hrms.data_source(),
            "personas": hrms.personas()}


@router.post("/chat")
async def chat(body: ChatIn):
    msg = body.message.strip()
    if not msg:
        raise HTTPException(400, "Message is empty")
    if len(msg) > 8000:
        raise HTTPException(413, "Message too long (8000 chars max)")
    s = get_session(body.session_id)
    s.persona = body.persona if body.persona in hrms.personas() else "employee"

    async def gen():
        try:
            async for ev in agent.run(s, msg):
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'text': f'Something went wrong: {exc}'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/upload")
async def upload(session_id: str = Form(...), kind: str = Form(""), file: UploadFile = File(...)):
    data = await file.read()
    try:
        text = extract_text(file.filename or "file.txt", data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not text.strip():
        raise HTTPException(422, "No readable text found (scanned PDFs are not supported yet).")
    doc = make_doc(file.filename or "document", text, kind or None)
    get_session(session_id).docs.append(doc)
    return {"id": doc.id, "name": doc.name, "kind": doc.kind, "chars": len(text), "chunks": len(doc.chunks)}


@router.delete("/upload/{doc_id}")
def remove_doc(doc_id: str, session_id: str):
    s = get_session(session_id)
    s.docs = [d for d in s.docs if d.id != doc_id]
    return {"ok": True}


@router.post("/approvals/{approval_id}")
def decide(approval_id: str, body: Decision):
    s = get_session(body.session_id)
    a = s.approvals.get(approval_id)
    if not a:
        raise HTTPException(404, "Approval not found")
    if body.decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve or reject")
    if body.content:
        a["content"] = body.content
    a["status"] = "approved" if body.decision == "approve" else "rejected"
    a["note"] = "Recorded only. Nothing was sent — copy the approved text into your HRMS / email." if a["status"] == "approved" else "Discarded."
    return a
