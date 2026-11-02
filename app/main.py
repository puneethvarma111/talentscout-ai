import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()
from ollama import Client
from faster_whisper import WhisperModel

from app.mcp_tools import discover_candidates
from app.agent import run_agent
from app.session import get_session
from app.store import list_candidates, set_stage
from app.supervisor_graph import run_supervisor
from app.copilot.router import router as copilot_router

BASE = Path(__file__).parent
ROOT = BASE.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"
MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA = Client(host="http://localhost:11434")
app = FastAPI(title="TalentScout AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if not FRONTEND_DIST.is_dir():
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

app.include_router(copilot_router)

whisper_model = None
last_candidates: list[dict[str, Any]] = []

class ChatRequest(BaseModel):
    message: str
    job_requirements: dict[str, Any] | None = None
    session_id: str | None = None
    use_supervisor: bool = False

class SearchRequest(BaseModel):
    role: str
    skills: list[str] = Field(default_factory=list)
    location: str = ""
    min_years: float = 0
    max_years: float = 99
    salary_min_lpa: float | None = None
    salary_max_lpa: float | None = None


class PipelineUpdate(BaseModel):
    stage: str

def ask_ollama(system: str, user: str) -> str:
    response = OLLAMA.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"temperature": 0.1},
    )
    return response.message.content or ""

def score_candidate(candidate: dict, req: SearchRequest) -> dict:
    text = " ".join(str(candidate.get(k) or "") for k in
                    ["name", "bio", "company", "title", "snippet", "url", "profile_url"]).lower()
    skills = req.skills or []
    matched = [s for s in skills if s.lower() in text]
    skill_score = (len(matched) / len(skills) * 70) if skills else 35
    location_score = 15 if req.location and req.location.lower() in text else (8 if not req.location else 0)
    role_text = req.role.lower().split()
    role_score = 15 if any(word in text for word in role_text if len(word) > 3) else 5
    score = round(min(100, skill_score + location_score + role_score))
    candidate.update({
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": [s for s in skills if s not in matched],
        "score_note": "Keyword/evidence heuristic; verify experience and skills from the source."
    })
    return candidate

@app.get("/api/health")
def health():
    try:
        models = OLLAMA.list()
        names = [m.model for m in models.models]
        return {
            "ok": True,
            "ollama_model": MODEL,
            "installed_models": names,
            "agent": "native tool calling",
            "supervisor": "langgraph hub-and-spoke",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "hint": "Start Ollama and ensure the model is pulled."}

@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    global whisper_model
    try:
        if whisper_model is None:
            whisper_model = WhisperModel(
                os.getenv("WHISPER_MODEL", "base"),
                device="cpu",
                compute_type="int8",
            )
        suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await audio.read())
            path = tmp.name
        try:
            segments, _ = whisper_model.transcribe(path, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            Path(path).unlink(missing_ok=True)
        return {"text": text}
    except Exception as exc:
        raise HTTPException(500, f"Transcription failed: {exc}")

@app.post("/api/search")
async def search(req: SearchRequest):
    global last_candidates
    raw = await discover_candidates(req.model_dump())
    last_candidates = [score_candidate(c, req) for c in raw]
    last_candidates.sort(key=lambda c: c["match_score"], reverse=True)
    return {"requirements": req.model_dump(), "candidates": last_candidates[:15]}


@app.post("/api/agent")
async def agent(req: ChatRequest):
    global last_candidates
    session_id = req.session_id or "default"
    session = get_session(session_id)
    try:
        if req.use_supervisor:
            result = run_supervisor(session, req.message, thread_id=session_id)
        else:
            result = await run_agent(OLLAMA, MODEL, session, req.message)
        last_candidates = result["candidates"]
        if last_candidates:
            from app.store import save_candidates

            save_candidates(last_candidates)
        return {"session_id": session_id, **result}
    except Exception as exc:
        raise HTTPException(503, f"Agent workflow failed: {exc}")


@app.post("/api/chat")
async def chat(req: ChatRequest):
    return await agent(req)


@app.get("/api/session")
def session_state(session_id: str = "default"):
    session = get_session(session_id)
    return {
        "session_id": session_id,
        "requirements": session.requirements,
        "candidates": session.candidates,
        "steps": session.agent_steps,
        "draft": session.last_draft,
        "checklist": session.last_checklist,
        "policy_refs": session.last_policy_refs,
        "management_brief": session.last_management_brief,
        "interview_pack": session.last_interview_pack,
    }


@app.get("/api/pipeline")
def pipeline():
    return {"candidates": list_candidates()}


@app.patch("/api/pipeline/{candidate_key:path}")
def update_pipeline(candidate_key: str, update: PipelineUpdate):
    if update.stage not in {"Sourced", "Shortlisted", "Outreach ready"}:
        raise HTTPException(400, "Invalid pipeline stage")
    set_stage(candidate_key, update.stage)
    return {"candidates": list_candidates()}

@app.post("/api/requirements")
def extract_requirements(req: ChatRequest):
    prompt = f"""
Extract recruitment criteria from this request.
Return ONLY valid JSON with keys:
role (string), skills (array of strings), location (string),
min_years (number), max_years (number),
salary_min_lpa (number or null), salary_max_lpa (number or null).
Use empty strings/arrays and 0/99 when unspecified. Do not invent values.
Request: {req.message}
"""
    try:
        raw = ask_ollama("You extract structured job criteria. Output JSON only.", prompt)
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end+1])
        return data
    except Exception:
        return {
            "role": req.message, "skills": [], "location": "",
            "min_years": 0, "max_years": 99,
            "salary_min_lpa": None, "salary_max_lpa": None,
            "needs_review": True
        }


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home():
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return index.read_text()
    return (BASE / "static" / "index.html").read_text()


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
