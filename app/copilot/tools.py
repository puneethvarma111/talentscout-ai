"""HR Copilot tools. Every tool returns a dict: summary (str), data, optional artifact / approval.

Guardrails enforced here (not just in the prompt):
- people-data tools check RBAC via hrms.resolve_employee / visible_ids
- resume text is PII-redacted before it is returned to the LLM
- "write" tools only create pending approvals; nothing is sent or saved to HRMS
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from app.copilot import hrms
from app.copilot.docs import Doc, redact_pii, search

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SKILL_VOCAB = [
    "python", "java", "spring boot", "javascript", "typescript", "react", "next.js", "node.js", "angular", "vue",
    "kotlin", "swift", "flutter", "react native", "go", "rust", "c++", "c#", ".net", "sql", "postgresql", "mysql",
    "mongodb", "redis", "kafka", "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "git",
    "microservices", "rest", "graphql", "machine learning", "llm", "pandas", "spark", "selenium", "playwright",
    "figma", "agile", "scrum", "payroll", "recruitment", "excel", "communication", "leadership", "system design",
]


@dataclass
class CopilotSession:
    id: str
    persona: str = "employee"
    messages: list[dict[str, Any]] = field(default_factory=list)
    docs: list[Doc] = field(default_factory=list)
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def actor(self) -> dict[str, Any]:
        return hrms.actor_for(self.persona)


_sessions: dict[str, CopilotSession] = {}


def get_session(session_id: str) -> CopilotSession:
    if session_id not in _sessions:
        _sessions[session_id] = CopilotSession(id=session_id)
    return _sessions[session_id]


# ---------------------------------------------------------------- tools

def search_hr_policy(s: CopilotSession, question: str) -> dict[str, Any]:
    hits = search(s.docs, question)
    if not hits:
        return {"summary": "No matching policy text found.", "data": {"matches": [], "instruction": "Tell the user it is not in the knowledge base and to confirm with HR. Do not guess."}}
    return {"summary": f"Found {len(hits)} policy passage(s)", "data": {"matches": hits, "instruction": "Answer only from these passages and cite them using the citation strings."}}


def get_leave_balance(s: CopilotSession, employee: str = "me") -> dict[str, Any]:
    emp = hrms.resolve_employee(s.actor, employee)
    bal = hrms.leave_balance(emp["id"])
    upcoming = hrms.leave_requests({emp["id"]})
    rows = [{"type": k, **v} for k, v in bal.items()] if isinstance(bal, dict) else bal
    return {
        "summary": f"Leave balance for {emp['name']}",
        "data": {"employee": emp["name"], "balances": rows, "requests": upcoming, "source": f"HRMS ({hrms.data_source()})", "as_of": hrms.as_of()},
        "artifact": {"kind": "table", "title": f"Leave balance — {emp['name']}", "columns": ["type", "entitled", "used", "available"], "rows": rows},
    }


def get_attendance_summary(s: CopilotSession, employee: str = "me") -> dict[str, Any]:
    if employee.lower() in ("team", "my team", "all"):
        ids = sorted(hrms.visible_ids(s.actor))
        emps = {e["id"]: e for e in hrms.employees()}
        rows = [{"employee": emps[i]["name"], **hrms.attendance(i)} for i in ids if i in emps]
        title = "Team attendance — last 30 days"
    else:
        emp = hrms.resolve_employee(s.actor, employee)
        rows = [{"employee": emp["name"], **hrms.attendance(emp["id"])}]
        title = f"Attendance — {emp['name']} (30 days)"
    flags = [f"{r['employee']}: {r.get('lop_days', 0)} LOP day(s)" for r in rows if r.get("lop_days")]
    flags += [f"{r['employee']}: {r.get('late_marks')} late marks" for r in rows if r.get("late_marks", 0) >= 3]
    return {
        "summary": f"Attendance for {len(rows)} employee(s)",
        "data": {"rows": rows, "flags": flags, "source": "HRMS attendance (demo)", "as_of": hrms.as_of()},
        "artifact": {"kind": "table", "title": title, "columns": ["employee", "present", "wfh", "late_marks", "lop_days", "avg_hours"], "rows": rows},
    }


def team_availability(s: CopilotSession, start: str = "", end: str = "") -> dict[str, Any]:
    if s.persona == "employee":
        raise hrms.AccessDenied("Team availability is available to managers and HR.")
    d0 = date.fromisoformat(start) if start else date.fromisoformat(hrms.as_of())
    d1 = date.fromisoformat(end) if end else d0 + timedelta(days=30)
    ids = hrms.visible_ids(s.actor)
    emps = {e["id"]: e["name"] for e in hrms.employees()}
    out = [
        {"employee": emps.get(r["employee_id"], r["employee_id"]), "type": r["type"], "from": r["from"], "to": r["to"], "status": r["status"]}
        for r in hrms.leave_requests(ids)
        if date.fromisoformat(r["from"]) <= d1 and date.fromisoformat(r["to"]) >= d0
    ]
    return {
        "summary": f"{len(out)} leave(s) between {d0} and {d1}",
        "data": {"range": [str(d0), str(d1)], "leaves": out, "pending": [o for o in out if o["status"] == "Pending"]},
        "artifact": {"kind": "table", "title": f"Who is out {d0} → {d1}", "columns": ["employee", "type", "from", "to", "status"], "rows": out},
    }


def people_insights(s: CopilotSession) -> dict[str, Any]:
    if s.persona == "employee":
        raise hrms.AccessDenied("People insights are available to managers and HR.")
    ids = hrms.visible_ids(s.actor) - {s.actor["user_id"]}
    rows = []
    for e in hrms.employees():
        if e["id"] not in ids:
            continue
        att, bal = hrms.attendance(e["id"]), hrms.leave_balance(e["id"])
        reasons, score = [], 0
        if e.get("overtime_hours_90d", 0) >= 60:
            score += 2; reasons.append(f"{e['overtime_hours_90d']}h overtime in 90 days (burnout risk)")
        earned = bal.get("Earned", {}) if isinstance(bal, dict) else {}
        if earned and earned.get("used", 0) == 0 and earned.get("entitled", 0) >= 12:
            score += 1; reasons.append("has not taken any earned leave this year")
        if not e.get("last_review") or e["last_review"] < "2026-01-01":
            score += 1; reasons.append("no performance conversation in the last cycle")
        if att.get("lop_days", 0) >= 2 or bal.get("Sick", {}).get("used", 0) >= 6:
            score += 1; reasons.append("unusual absence pattern (LOP / sick leave)")
        t = hrms.tenure_years(e.get("joining_date"))
        if 2.5 <= t <= 4.5:
            score += 1; reasons.append(f"{t} yrs tenure (common move window)")
        level = "High" if score >= 3 else "Medium" if score == 2 else "Low"
        rows.append({"employee": e["name"], "designation": e["designation"], "signal": level, "reasons": "; ".join(reasons) or "no notable signals"})
    rows.sort(key=lambda r: {"High": 0, "Medium": 1, "Low": 2}[r["signal"]])
    return {
        "summary": f"Reviewed {len(rows)} team member(s)",
        "data": {"rows": rows, "method": "Rule-based signals: overtime, unused leave, review recency, absence pattern, tenure. No protected attributes used.", "caveat": "Signals are conversation starters, not predictions or grounds for action."},
        "artifact": {"kind": "table", "title": "Retention signals (conversation starters)", "columns": ["employee", "designation", "signal", "reasons"], "rows": rows},
    }


def _find_doc(s: CopilotSession, kind: str) -> Doc | None:
    return next((d for d in reversed(s.docs) if d.kind == kind), None)


def _extract_skills(text: str) -> list[str]:
    low = text.lower()
    return [sk for sk in SKILL_VOCAB if re.search(r"(?<![a-z])" + re.escape(sk) + r"(?![a-z])", low)]


def screen_resume(s: CopilotSession, resume_text: str = "", job_description: str = "", must_have: list[str] | None = None,
                  nice_to_have: list[str] | None = None, min_years: float = 0) -> dict[str, Any]:
    resume_doc = _find_doc(s, "resume")
    jd_doc = _find_doc(s, "jd")
    resume = resume_text or (resume_doc.text if resume_doc else "")
    jd = job_description or (jd_doc.text if jd_doc else "")
    if not resume.strip():
        return {"summary": "No resume provided", "data": {"error": "Ask the user to upload a resume (.pdf/.txt) or paste it."}}
    must = [m.lower() for m in (must_have or [])] or _extract_skills(jd)[:8]
    nice = [m.lower() for m in (nice_to_have or []) if m.lower() not in must]
    if not must:
        return {"summary": "No requirements to compare against", "data": {"error": "Ask for the job description or the must-have skills."}}
    if not min_years:
        m = re.search(r"(\d+)\+?\s*(?:-\s*\d+\s*)?years", jd.lower())
        min_years = float(m.group(1)) if m else 0
    lines = [l.strip() for l in redact_pii(resume).splitlines() if l.strip()]

    def evidence(skill: str) -> str | None:
        pat = re.compile(r"(?<![a-z])" + re.escape(skill) + r"(?![a-z])", re.I)
        return next((l[:160] for l in lines if pat.search(l)), None)

    must_rows = [{"requirement": sk, "type": "must", "met": bool(ev := evidence(sk)), "evidence": ev or "—"} for sk in must]
    nice_rows = [{"requirement": sk, "type": "nice", "met": bool(ev := evidence(sk)), "evidence": ev or "—"} for sk in nice]
    yrs = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\+?\s*years", resume.lower())]
    years = max(yrs) if yrs else None
    must_pct = sum(r["met"] for r in must_rows) / len(must_rows)
    nice_pct = (sum(r["met"] for r in nice_rows) / len(nice_rows)) if nice_rows else 1
    exp_ok = 1.0 if not min_years else (min(1.0, (years or 0) / min_years))
    score = round(must_pct * 60 + nice_pct * 15 + exp_ok * 25)
    rec = "Advance to interview" if score >= 75 and must_pct >= 0.75 else "Hold — clarify gaps in screen call" if score >= 50 else "Not a match on stated requirements"
    gaps = [r["requirement"] for r in must_rows if not r["met"]]
    probes = [f"The resume doesn't mention {g}. Ask: 'Tell me about any hands-on work with {g}.'" for g in gaps[:3]]
    probes += [f"Verify depth: 'Walk me through the {r['requirement']} work in: {r['evidence'][:70]}…'" for r in must_rows if r["met"]][:2]
    rows = must_rows + nice_rows
    return {
        "summary": f"Screened resume: {score}/100",
        "data": {
            "score": score, "recommendation": rec, "breakdown": {"must_have": f"{must_pct:.0%} (60 pts)", "nice_to_have": f"{nice_pct:.0%} (15 pts)", "experience": f"{years or 'not stated'} yrs vs {min_years or 'none'} required (25 pts)"},
            "requirements": rows, "gaps": gaps, "interview_probes": probes,
            "sources": {"resume": resume_doc.name if resume_doc and not resume_text else "pasted text", "jd": jd_doc.name if jd_doc and not job_description else ("pasted text" if jd else "stated skills")},
            "caveat": "Keyword evidence only; contact details redacted. A human makes the decision.",
        },
        "artifact": {"kind": "scorecard", "title": "Resume screening", "score": score, "recommendation": rec, "columns": ["requirement", "type", "met", "evidence"], "rows": rows, "notes": probes},
    }


def create_onboarding_plan(s: CopilotSession, role: str, new_hire_name: str = "New hire", start_date: str = "") -> dict[str, Any]:
    templates = json.loads((DATA_DIR / "onboarding_templates.json").read_text())
    fam = "engineering" if re.search(r"engineer|developer|devops|qa|software", role.lower()) else "general"
    items = list(templates.get(fam, templates["general"]))
    items += [
        {"task": "Issue offer acceptance, ID proofs and bank/PF/statutory details collection", "owner": "HR", "due": "Before day 1"},
        {"task": "Assign onboarding buddy and share 30-60-90 day plan", "owner": "Manager", "due": "Day 1"},
        {"task": "Enroll in payroll, leave policy and attendance system", "owner": "HR", "due": "Day 1"},
        {"task": "30-day check-in (fit, blockers, feedback)", "owner": "HR + Manager", "due": "Day 30"},
    ]
    start = date.fromisoformat(start_date) if start_date else None
    rows = [{"task": i["task"], "owner": i["owner"], "due": i["due"] + (f" ({start})" if start and i["due"].startswith("Day 1") else "")} for i in items]
    return {
        "summary": f"{len(rows)}-step onboarding plan for {new_hire_name}",
        "data": {"role": role, "new_hire": new_hire_name, "items": rows, "source": "onboarding_templates.json + standard India HR steps"},
        "artifact": {"kind": "checklist", "title": f"Onboarding — {new_hire_name} ({role})", "columns": ["task", "owner", "due"], "rows": rows},
    }


def draft_offer_letter(s: CopilotSession, candidate_name: str, role: str, ctc_lpa: float | None = None, joining_date: str = "", location: str = "") -> dict[str, Any]:
    if s.persona != "hr":
        raise hrms.AccessDenied("Only HR can draft offer letters.")
    missing = [k for k, v in {"ctc_lpa": ctc_lpa, "joining_date": joining_date, "location": location}.items() if not v]
    ctc = f"₹{ctc_lpa:g} LPA" if ctc_lpa else "[CTC — to be confirmed]"
    body = (
        f"Dear {candidate_name},\n\n"
        f"We are pleased to offer you the position of {role} at our company, based in {location or '[location]'}.\n\n"
        f"Annual CTC: {ctc} (detailed break-up in Annexure A)\n"
        f"Date of joining: {joining_date or '[joining date]'}\n"
        "Probation: 6 months, as per company policy\n"
        "Notice period: as per company policy\n\n"
        "This offer is subject to satisfactory background verification and submission of the documents listed in Annexure B.\n"
        "Please confirm your acceptance by signing and returning this letter within 7 days.\n\n"
        "Warm regards,\nHuman Resources"
    )
    aid = uuid.uuid4().hex[:8]
    approval = {"id": aid, "action": "Send offer letter", "target": candidate_name, "status": "pending", "content": body, "missing_fields": missing}
    s.approvals[aid] = approval
    return {
        "summary": "Offer letter drafted — waiting for your approval",
        "data": {"approval_id": aid, "missing_fields": missing, "note": "Draft only. Not sent. HR must review CTC, legal clauses and approve."},
        "approval": approval,
    }


def draft_interview_questions(s: CopilotSession, role: str, focus: str = "") -> dict[str, Any]:
    from app.agent_tools import generate_interview_pack
    from app.session import AgentSession

    tmp = AgentSession()
    tmp.requirements["role"] = role
    pack = json.loads(generate_interview_pack(tmp, role=role, focus=focus))
    rows = [{"section": sec, "question": q} for sec, qs in pack["sections"].items() for q in qs]
    return {"summary": f"{len(rows)} interview questions", "data": pack, "artifact": {"kind": "table", "title": f"Interview pack — {role}", "columns": ["section", "question"], "rows": rows}}


# ---------------------------------------------------------------- registry

def _fn(name: str, desc: str, props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": required or []}}}


S = {"type": "string"}
TOOLS: dict[str, tuple[Callable[..., dict[str, Any]], dict[str, Any], str]] = {
    "search_hr_policy": (search_hr_policy, _fn("search_hr_policy", "Search uploaded HR handbooks and company policies. Use for any policy / rules / entitlement question.", {"question": S}, ["question"]), "Searching HR policies"),
    "get_leave_balance": (get_leave_balance, _fn("get_leave_balance", "Get leave balances and leave requests for an employee. employee='me' for the current user, or a name/id.", {"employee": S}), "Checking leave balance"),
    "get_attendance_summary": (get_attendance_summary, _fn("get_attendance_summary", "30-day attendance (present, WFH, late marks, LOP). employee='me', a name/id, or 'team'.", {"employee": S}), "Reading attendance"),
    "team_availability": (team_availability, _fn("team_availability", "Who is on leave in a date range (YYYY-MM-DD). Managers/HR only.", {"start": S, "end": S}), "Checking team availability"),
    "people_insights": (people_insights, _fn("people_insights", "Team retention / burnout signals with reasons. Managers/HR only.", {}), "Analysing team signals"),
    "screen_resume": (screen_resume, _fn("screen_resume", "Score an uploaded or pasted resume against a job description or must-have skills, with evidence and gaps.", {"resume_text": S, "job_description": S, "must_have": {"type": "array", "items": S}, "nice_to_have": {"type": "array", "items": S}, "min_years": {"type": "number"}}), "Screening resume"),
    "create_onboarding_plan": (create_onboarding_plan, _fn("create_onboarding_plan", "Create an onboarding checklist for a new hire.", {"role": S, "new_hire_name": S, "start_date": S}, ["role"]), "Building onboarding plan"),
    "draft_offer_letter": (draft_offer_letter, _fn("draft_offer_letter", "Draft an offer letter. Creates a pending approval; never sends. HR only.", {"candidate_name": S, "role": S, "ctc_lpa": {"type": "number"}, "joining_date": S, "location": S}, ["candidate_name", "role"]), "Drafting offer letter"),
    "draft_interview_questions": (draft_interview_questions, _fn("draft_interview_questions", "Generate a structured interview question pack.", {"role": S, "focus": S}, ["role"]), "Preparing interview questions"),
}


def tool_schemas() -> list[dict[str, Any]]:
    return [t[1] for t in TOOLS.values()]


def run_tool(s: CopilotSession, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name not in TOOLS:
        return {"summary": f"Unknown tool {name}", "data": {"error": "unknown tool"}, "ok": False}
    fn = TOOLS[name][0]
    try:
        allowed = TOOLS[name][1]["function"]["parameters"]["properties"].keys()
        res = fn(s, **{k: v for k, v in (args or {}).items() if k in allowed and v not in (None, "")})
        res["ok"] = "error" not in res.get("data", {})
        return res
    except hrms.AccessDenied as exc:
        return {"summary": "Access denied", "data": {"error": str(exc)}, "ok": False}
    except (LookupError, ValueError, TypeError) as exc:
        return {"summary": "Could not complete", "data": {"error": str(exc)}, "ok": False}
