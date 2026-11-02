# HR Copilot — build report (2 Nov 2026)

## What was built
- **Backend** `app/copilot/`: 9 tools (policy Q&A with citations, leave balance, attendance, who's out, retention signals, resume screening vs JD, onboarding plan, offer-letter draft, interview pack). Role-based access per persona (Employee = self, Manager = own team, HR = all), PII redaction of resumes, approval cards for drafts (never sent), bounded 5-round tool loop, SSE streaming, provider switch (Ollama / OpenAI-compatible / offline mock) with fallback to mock if the model fails.
- **API**: `GET /api/copilot/config`, `POST /api/copilot/chat` (SSE), `POST /api/copilot/upload` (.pdf/.txt/.md/.csv, 5 MB max), `DELETE /api/copilot/upload/{id}`, `POST /api/copilot/approvals/{id}` (records decision only).
- **UI**: new default "HR Copilot" tab (old workspace = "Sourcing" tab): persona switch, use-case cards per role, streaming answers with citation chips, collapsible tool-step list, tables / checklist / score ring with CSV export, editable approval card, file chips, offline banner, stop/retry, ARIA labels, mobile layout, reduced-motion support.
- **Demo data** `app/data/hrms_demo.json` (synthetic, shaped like hrms_core).
- **Tests** `tests/test_copilot.py` (6 unit tests).

## Run
```bash
uv sync
uv run uvicorn app.main:app --reload          # API :8000
cd frontend && npm install && npm run dev     # UI :5173
LLM_PROVIDER=mock uv run uvicorn app.main:app --reload   # offline demo, no model
uv run python -m unittest tests.test_copilot
```

## Env vars (all optional)
| Var | Meaning |
|---|---|
| LLM_PROVIDER | auto (default) / ollama / openai / mock |
| COPILOT_MODEL | Ollama model override (default OLLAMA_MODEL) |
| OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL | any OpenAI-compatible endpoint |
| HRMS_DATA_SOURCE | demo (default) / live |
| HRMS_MASTER_DATA_URL, HRMS_TIME_MANAGEMENT_URL | hrms_core service URLs (default :8001 / :8008) |
| HRMS_API_TOKEN, HRMS_TENANT_ID | Bearer JWT + X-Tenant-ID for live mode |

## Validation
- Typecheck + build pass; oxlint: no new warnings (1 pre-existing in ContextRail.tsx).
- Unit tests 6/6 pass.
- Routes 200: `/`, `/api/health`, `/api/copilot/config`; Vite `/`.
- Mock mode via API: leave balance, retention signals, offer letter blocked for Manager, resume upload + screening.
- Ollama qwen3.5:4b: leave balance (~6 s) and cited remote-work policy answer (~4 s).
- Home screen checked in a headless Chrome screenshot.

## Not tested
- Clicking through a chat in a real browser.
- Ollama on offer letter / access-denied / multi-tool questions.
- OpenAI-compatible provider.
- Live hrms_core mode (field names are guesses; leave requests and attendance still use demo data in live mode).
- Scanned PDFs (not supported).

## Known limits / decisions
- Sessions, uploads and approvals are in memory (lost on restart).
- Persona switch is a demo; real use should take the user from the HRMS JWT.
- Retention signals are rule-based conversation starters, not predictions.
