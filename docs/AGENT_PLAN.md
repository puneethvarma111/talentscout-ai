# HR Copilot — agent plan

Extend (not rewrite) TalentScout with an **HR Copilot**: a streaming, tool-calling agent for day-to-day HRMS work.
The existing recruiting workspace stays as a second tab.

## Use cases (real-world)
1. **Resume screening vs JD** — paste/upload resume + JD → explainable score (must-have, nice-to-have, experience), evidence lines quoted from the resume, gaps, suggested interview probes. PII (email/phone) redacted before the LLM sees it.
2. **Policy Q&A with citations** — answers only from uploaded handbook files + built-in policies, citing `[doc §chunk]`. Says "not found" instead of guessing.
3. **Leave & attendance** — leave balance, upcoming leave, attendance/late/LOP summary for an employee or a team. RBAC: Employee sees self only; Manager sees their team; HR sees all.
4. **Team availability** — who is out in a date range (sprint / release planning).
5. **Attrition & people insights** — team-level risk signals (tenure, leave pattern, overtime, last-review) with reasons; never uses protected attributes; framed as conversation starters.
6. **Onboarding plan** — role-based checklist (reuses existing templates) with owners/dates.
7. **Offer letter / HR letter drafts** — draft only, returned as a **pending approval** card. Nothing is sent.
8. **Interview pack** — reuses existing `generate_interview_pack`.

## Design
- `app/copilot/` package: `llm.py` (providers), `tools.py` (tool registry + JSON schemas), `hrms.py` (data source: demo JSON or live hrms_core, read-only GET), `docs.py` (upload + chunk + keyword retrieval), `agent.py` (bounded loop, max 5 rounds), `mock.py` (offline intent router), `router.py` (FastAPI routes).
- Providers via `LLM_PROVIDER` = `auto` (default: Ollama if reachable, else mock) | `ollama` | `openai` (any OpenAI-compatible: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`) | `mock`.
- Streaming: `POST /api/copilot/chat` returns Server-Sent Events: `step` (tool start/done with args + summary), `token`, `artifact`, `approval`, `done`, `error`.
- Guardrails: system prompt forbids inventing data; tools return `source` fields; RBAC check inside every people-data tool; PII redaction; write-like actions only create `pending` approvals (`POST /api/copilot/approvals/{id}` approve/reject just records the decision — no email/HRMS write).
- UI: new "HR Copilot" view — persona selector (Employee / Manager / HR), use-case cards with suggested prompts, streaming bubbles with light markdown, collapsible tool-step timeline, artifact + approval cards, file upload chips (.txt/.md/.pdf), empty/loading/error states, mock-mode banner, keyboard + screen-reader friendly, responsive.
