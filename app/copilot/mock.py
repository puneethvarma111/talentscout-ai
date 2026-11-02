"""Offline mode: deterministic intent router + templated answers. Lets the UI be demoed without any LLM."""
from __future__ import annotations

import re
from typing import Any

from app.copilot.tools import SKILL_VOCAB


def route(message: str, has_resume: bool) -> list[tuple[str, dict[str, Any]]]:
    m = message.lower()
    name = re.search(r"(?:for|of)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", message)
    who = name.group(1) if name and name.group(1).lower() not in ("me", "my", "the", "a") else "me"
    if "team" in m and ("attendance" in m or "late" in m):
        return [("get_attendance_summary", {"employee": "team"})]
    if any(w in m for w in ("resume", "cv", "screen", "candidate fit")) or (has_resume and "match" in m):
        skills = [s for s in SKILL_VOCAB if re.search(r"(?<![a-z])" + re.escape(s) + r"(?![a-z])", m)]
        return [("screen_resume", {"must_have": skills} if skills else {})]
    if "offer" in m:
        role = re.search(r"(?:as|for)\s+(?:an?\s+)?([a-z ]*?(?:engineer|manager|developer|analyst|designer|executive))", m)
        ctc = re.search(r"(\d+(?:\.\d+)?)\s*(?:lpa|lakh)", m)
        cand = re.search(r"(?:to|for)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", message)
        return [("draft_offer_letter", {"candidate_name": cand.group(1) if cand else "Candidate", "role": role.group(1).strip().title() if role else "Software Engineer", "ctc_lpa": float(ctc.group(1)) if ctc else None})]
    if any(w in m for w in ("attrition", "retention", "burnout", "flight risk", "insight")):
        return [("people_insights", {})]
    if any(w in m for w in ("who is out", "availability", "on leave next", "who's out", "out next")):
        return [("team_availability", {})]
    if "onboard" in m:
        role = re.search(r"(?:for|as)\s+(?:a|an|our)?\s*(?:new\s+)?([a-z ]+?)(?:\s+starting|\s+joining|$|\.|,)", m)
        return [("create_onboarding_plan", {"role": role.group(1).strip().title() if role else "Software Engineer"})]
    if "interview" in m or "questions" in m:
        role = re.search(r"for\s+(?:a|an)?\s*([a-z ]+?)(?:\s+focus|\s+with|$|\.|,)", m)
        return [("draft_interview_questions", {"role": role.group(1).strip().title() if role else "Software Engineer"})]
    if "attendance" in m or "late" in m or "lop" in m:
        return [("get_attendance_summary", {"employee": who})]
    if "balance" in m or ("leave" in m and any(w in m for w in ("how many", "left", "remaining", "my leave"))):
        return [("get_leave_balance", {"employee": who})]
    return [("search_hr_policy", {"question": message})]


def answer(results: list[tuple[str, dict[str, Any]]]) -> str:
    parts = []
    for name, r in results:
        d = r.get("data", {})
        if "error" in d:
            parts.append(f"**I couldn't complete that.** {d['error']}")
            continue
        if name == "search_hr_policy":
            if not d.get("matches"):
                parts.append("I couldn't find this in the HR knowledge base. Please upload the relevant policy or confirm with HR — I won't guess.")
            else:
                top = d["matches"][:2]
                parts.append("Here's what the policy says:\n\n" + "\n\n".join(f"> {t['text'][:400]}\n{t['citation']}" for t in top) + "\n\n_Confirm edge cases with HR._")
        elif name == "get_leave_balance":
            lines = [f"- **{b['type']}**: {b.get('available', '?')} of {b.get('entitled', '?')} days left" for b in d.get("balances", [])]
            req = [f"- {q['type']} {q['from']} → {q['to']} ({q['status']})" for q in d.get("requests", [])]
            parts.append(f"**{d['employee']}** — leave as of {d['as_of']}:\n" + "\n".join(lines) + (("\n\nUpcoming / pending:\n" + "\n".join(req)) if req else ""))
        elif name == "get_attendance_summary":
            flags = d.get("flags") or ["No LOP or repeated late marks."]
            parts.append("Attendance for the last 30 days is in the table. Things to look at:\n" + "\n".join(f"- {f}" for f in flags))
        elif name == "team_availability":
            pend = d.get("pending", [])
            parts.append(f"{len(d['leaves'])} leave(s) overlap {d['range'][0]} → {d['range'][1]}." + (f" **{len(pend)} still need your approval.**" if pend else ""))
        elif name == "people_insights":
            hi = [r for r in d["rows"] if r["signal"] != "Low"]
            parts.append("Team signals worth a 1:1 conversation:\n" + ("\n".join(f"- **{r['employee']}** ({r['signal']}): {r['reasons']}" for r in hi) or "- Nothing notable.") + f"\n\n_{d['caveat']}_")
        elif name == "screen_resume":
            parts.append(f"**Score {d['score']}/100 — {d['recommendation']}.**\n\n- Must-haves: {d['breakdown']['must_have']}\n- Nice-to-haves: {d['breakdown']['nice_to_have']}\n- Experience: {d['breakdown']['experience']}\n" + (f"\nGaps: {', '.join(d['gaps'])}" if d["gaps"] else "") + f"\n\n_{d['caveat']}_")
        elif name == "create_onboarding_plan":
            parts.append(f"I've built a {len(d['items'])}-step onboarding plan for the {d['role']} role. Adjust owners and dates as needed.")
        elif name == "draft_offer_letter":
            miss = d.get("missing_fields")
            parts.append("I've drafted the offer letter. **It has not been sent** — review it in the approval card." + (f" Missing: {', '.join(miss)}." if miss else ""))
        elif name == "draft_interview_questions":
            parts.append(f"Here's an interview pack for {d['role']} covering screening, technical, behavioral and closing questions.")
    return "\n\n".join(parts)
