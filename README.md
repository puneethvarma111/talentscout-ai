# Local Research AI

Local Deep Research AI Agent using **LangChain**, **ChatOllama**, and **Ollama** (`llama3.2:3b` by default). The agent plans research, searches the web, extracts page content, runs an **IterDRAG-style** summarize/reflect loop (adapted from [langchain-ai/local-deep-researcher](https://github.com/langchain-ai/local-deep-researcher); see [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md)), and produces a cited Markdown report.

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com/) running locally with your model pulled — check names with `ollama list`, then set `OLLAMA_MODEL` in `.env` (this repo defaults to `llama3.2:3b`)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

```bash
cp .env.example .env
# Match OLLAMA_MODEL to an entry from: ollama list
uv sync --extra dev
```

## Run

**API:**

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Streamlit UI (dark, chat-style):**

```bash
uv run streamlit run frontend/streamlit_app.py
```

Use the **chat input** at the bottom to start research. While research runs, the UI subscribes to **`GET /api/research/{id}/events`** (SSE) for live stage lines and a **streaming running summary** in the assistant bubble (poll fallback if SSE fails). When complete, open **Summary**, **Full report**, **Sources**, or **Export** tabs. Sidebar: **New research**, history grouped by day, API/Ollama status, delete (×) on history rows.

Keep the **API running in a separate terminal** while using Streamlit.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | App + Ollama health |
| POST | `/api/research` | Start research (`{"question": "..."}`) |
| GET | `/api/research/{id}` | Session status |
| GET | `/api/research/{id}/report` | Markdown report + references |
| GET | `/api/research/{id}/report.pdf` | PDF export |
| GET | `/api/research/{id}/events` | SSE stream |
| GET | `/api/research/{id}/events/poll` | JSON event poll |
| GET | `/api/research/history` | Past sessions |
| DELETE | `/api/research/{id}` | Delete session |

## Configuration

See [`.env.example`](.env.example) for Ollama, iteration limits, research mode, streaming, and SQLite path.

### Performance (speed-first)

For shorter runs on small local models (e.g. `llama3.2:3b`), use a fast profile in `.env`:

```bash
RESEARCH_MODE=fast
OLLAMA_MODEL=llama3.2:3b
MAX_RESEARCH_ITERATIONS=1
MAX_PAGES_PER_ITERATION=2
MAX_SEARCH_RESULTS=5
FETCH_FULL_PAGE=false
USE_LDR_LOOP=true
```

Fast mode skips LLM per-page extraction (heuristic findings only), caps iterations/pages/queries, and tightens Ollama `num_ctx` / `num_predict` and structured-output retries. Expect **~4–6 LLM calls** per question vs **~15–25** in balanced mode—faster, with a summary-driven report and coarser cited findings.

Keep Ollama running with the model already pulled so the first request avoids cold-load delay.

### Live updates

- Backend emits `summary_delta`, `activity`, and stage events into SQLite; SSE delivers them to the UI.
- `ENABLE_SUMMARY_STREAMING=true` streams the running summary from Ollama during each iteration.
- `SSE_POLL_INTERVAL_SEC` controls how often the API SSE loop checks for new events (default `0.4`).

## Tests

```bash
uv run pytest -q
```

Tests mock LLM and HTTP; no live Ollama or network required.

## Architecture

Deterministic pipeline in `app/research/research_service.py` (plan → search → extract → gap loop → report). Optional bounded tool loop in `app/agent/execution_loop.py` with deterministic fallbacks for small models. SQLite persistence under `data/`. Reports saved to `reports/`.

## Restrictions

No LangGraph, CrewAI, cloud LLM APIs, or arbitrary code execution tools.
