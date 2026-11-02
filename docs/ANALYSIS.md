# TalentScout AI — repository analysis (2 Nov 2026)

## What it is
A local-first **recruiting + HR assistant** ("TalentScout HR"). It sources public candidates
(GitHub / web via an MCP server), ranks them with a keyword heuristic, and drafts JDs,
outreach, interview packs, onboarding checklists, salary bands and policy answers.

## Stack
| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI + Uvicorn (`app/main.py`), managed by `uv` |
| LLM | Ollama (`OLLAMA_MODEL`, default `qwen3.5:4b`) via `ollama` client, native tool calling |
| Orchestration | Single tool loop (`app/agent.py`) or LangGraph supervisor with Recruiting / HR Ops / Policy workers (`app/supervisor_graph.py`) |
| Tools | `app/agent_tools.py` (12 tools), MCP stdio server `mcp_server/server.py` (GitHub/web search) |
| Memory | In-process sessions (`app/session.py`), SQLite pipeline `talentscout.sqlite3`, LangGraph checkpoints `agent_memory.sqlite` |
| Voice | faster-whisper `/api/transcribe` + browser SpeechSynthesis |
| Frontend | React 19 + TypeScript 7 + Vite 8, oxlint, plain CSS (`src/styles/app.css`, teal `#087f73` palette, Inter) — no component library |
| Other UIs | Legacy static UI `app/static/`, Streamlit lab `streamlit_app/` |

## How it runs
`uv run uvicorn app.main:app --reload` (API :8000) and `cd frontend && npm run dev` (:5173, proxies `/api`).

## Gaps found
- Request/response only — no streaming, tool steps shown as one line after the fact.
- HR data is static JSON (4 policies, 2 onboarding templates); no employee, leave or attendance data,
  no link to the real Swiftlyy HRMS (`hrms_core`).
- No document upload: policy Q&A cannot use the company's real handbook; no citations.
- No resume screening against a JD (sourcing only works on public GitHub profiles).
- No approval step: drafts are returned but there is no explicit "pending approval" object.
- No offline/mock mode: UI is unusable when Ollama is down.
- `frontend/src/App.css` and `index.css` are unused Vite template styles.
- No tests.

## Real HRMS APIs (read-only reference: `~/Desktop/hrms_core`)
- master-data :8001 `GET /api/v1/masterdata/employees`, `/employees/{id}`, `/departments`
- time-management :8008 `GET /api/leaves/employee/{employeeId}`, `/balance`, `/daily`, `/api/attendance/payroll-summary`
- Auth: `Authorization: Bearer <JWT>` + `X-Tenant-ID` (same as hrms-agent-service "Kai").
