# TalentScout AI (local MVP)

Local-first **auto-recruit HR agent** for recruiters, hiring managers, and people ops — inspired by the [my-first-agent](https://github.com/vchirrav-eng/my-first-agent) LangGraph + MCP supervisor pattern, adapted for hiring workflows.

## What it does (HR & management use cases)

| Use case | Who it helps | What the agent does |
|----------|--------------|---------------------|
| **Auto-recruit sourcing** | Recruiters | Parses role criteria, searches public GitHub/web (MCP), ranks by observable evidence, shows shortlist |
| **Job description drafts** | HR / hiring managers | Generates reviewable JDs from the live hiring brief |
| **Outreach drafts** | Recruiters | Evidence-grounded messages — **never sent automatically** |
| **Interview packs** | Hiring managers | Screening, technical, behavioral, and closing questions from skills/role |
| **Candidate comparison** | Hiring committee | Top-N pros/gaps from public evidence heuristics |
| **Pipeline summary** | Leadership | Stage counts and top profiles from the local SQLite pipeline |
| **Salary band guidance** | HR / finance planning | Indicative local bands (planning only, not offers) |
| **Onboarding checklists** | HR ops | Role-based checklists from local templates |
| **Policy Q&A** | Employees / HR | Leave, remote, holidays, benefits from local `hr_policies.json` |

## Architecture (aligned with my-first-agent)

Seven-step local agent framework:

1. **System prompt** — Role, safety, and “human-in-the-loop” rules (`app/agent.py`, worker prompts in `app/supervisor_graph.py`)
2. **LLM** — Ollama (`OLLAMA_MODEL`, default `qwen3.5:4b`)
3. **Tools** — Recruiting, HR ops, and policy tools (`app/agent_tools.py`) + MCP public search (`mcp_server/server.py`)
4. **Memory** — Session state (`app/session.py`), pipeline DB (`talentscout.sqlite3`), LangGraph checkpoints (`agent_memory.sqlite`)
5. **Orchestration** — Single-agent tool loop **or** LangGraph supervisor (Recruiting / HR Ops / Policy workers)
6. **UI** — React + TypeScript workspace (`frontend/`), legacy static fallback (`app/static/`), optional Streamlit supervisor page
7. **Evals** — Optional LangSmith via env vars (same pattern as the reference repo)

```text
                    ┌─────────────┐
                    │ Supervisor  │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
   Recruiting_Agent   HR_Ops_Agent   Policy_Agent
           │               │               │
      MCP + rank      JD / onboarding   policy + pipeline
```

## Requirements

- macOS Apple Silicon (tested target)
- Python 3.12 via [uv](https://github.com/astral-sh/uv)
- Ollama running locally
- `ollama pull qwen3.5:4b`

## Setup

```bash
brew install uv
uv python install 3.12
uv sync
cp .env.example .env
ollama serve
```

### Primary UI (React + TypeScript)

Terminal 1 — API:

```bash
uv run uvicorn app.main:app --reload
```

Terminal 2 — frontend dev server (proxies `/api` to the API):

```bash
cd frontend && npm install && npm run dev
```

Open http://127.0.0.1:5173 — enable **Multi-agent supervisor (LangGraph)** for the hub-and-spoke workflow (default on).

Production-style (single port): build the frontend, then run only Uvicorn:

```bash
cd frontend && npm run build
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 (serves `frontend/dist` when present; otherwise falls back to legacy `app/static/`).

### Legacy static UI (no Node)

If `frontend/dist` is missing, http://127.0.0.1:8000 serves the original HTML/JS workspace under `app/static/`.

### CLI supervisor (reference-style, no web server)

```bash
uv run python -m app.cli_agent
```

### Streamlit supervisor lab

```bash
uv run streamlit run streamlit_app/Home.py
```

Open the **Supervisor Agent** page for pre-built HR scenarios.

### Legacy comparison UI

Same Streamlit app — Workspace, Evidence, Compare, Pipeline, Export pages.

## Voice

Microphone → local **faster-whisper** transcription → agent reply → browser **SpeechSynthesis** readback.

## MCP tools

Stdio MCP server (`mcp_server/server.py`):

- `github_search_users`
- `public_web_search`
- `github_list_user_repos`

Set `GITHUB_TOKEN` in `.env` for higher GitHub rate limits.

## API

- `POST /api/agent` — body: `{ "message", "session_id", "use_supervisor": true }`
- `GET /api/session`, `GET /api/pipeline`, `PATCH /api/pipeline/{key}`

## Important

- Learning MVP — not a production ATS or hiring decision engine.
- Public profiles can be incomplete; verify at the source.
- No protected characteristics or proxies in ranking.
- Scores are explainable heuristics, not performance predictions.
- Humans approve outreach, offers, and hires.
- Respect platform terms, privacy law, and API rules.
