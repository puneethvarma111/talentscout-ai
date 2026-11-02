import json
from pathlib import Path
from typing import Any

from app.mcp_tools import discover_candidates, mcp_session
from app.session import AgentSession, DEFAULT_REQUIREMENTS
from app.store import list_candidates

DATA_DIR = Path(__file__).resolve().parent / "data"


def set_job_requirements(session: AgentSession, **values: Any) -> str:
    """Save explicit job criteria extracted from the recruiter's request."""
    requirements = DEFAULT_REQUIREMENTS.copy()
    requirements.update(session.requirements)
    for key in requirements:
        if key in values and values[key] is not None:
            requirements[key] = values[key]
    requirements["skills"] = [
        str(skill).strip()
        for skill in requirements.get("skills", [])
        if str(skill).strip()
    ]
    session.requirements = requirements
    return json.dumps(requirements, ensure_ascii=False)


async def search_candidates(session: AgentSession) -> str:
    """Search public GitHub and web sources using the saved job criteria."""
    if not session.requirements.get("role") and not session.requirements.get("skills"):
        return json.dumps({"error": "Need a role or at least one skill before searching."})
    session.candidates = await discover_candidates(session.requirements)
    async with mcp_session() as bridge:
        for candidate in session.candidates[:8]:
            username = candidate.get("username")
            if not username or username in session.enrichment:
                continue
            try:
                repos = await bridge.call_tool(
                    "github_list_user_repos", {"username": username, "limit": 8}
                )
                session.enrichment[username] = repos if isinstance(repos, list) else []
                candidate["repositories"] = session.enrichment[username]
            except Exception:
                candidate["repositories"] = []
    session.agent_steps.append(
        f"Sourced {len(session.candidates)} public profiles and enriched GitHub evidence"
    )
    return json.dumps(
        {"count": len(session.candidates), "candidates": session.candidates[:20]},
        ensure_ascii=False,
    )


def _rank(candidate: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("name", "bio", "company", "title", "snippet", "location")
    ).lower()
    repositories = candidate.get("repositories") or []
    repo_text = " ".join(
        str(repo.get(key) or "") for repo in repositories for key in ("name", "language", "description")
    ).lower()
    skills = requirements.get("skills") or []
    matched = [skill for skill in skills if skill.lower() in f"{text} {repo_text}"]
    score = (len(matched) / len(skills) * 70 if skills else 35)
    location = str(requirements.get("location") or "").lower()
    location_score = 15 if location and location in text else (8 if not location else 0)
    role_words = [word for word in str(requirements.get("role") or "").lower().split() if len(word) > 3]
    role_score = 15 if any(word in text for word in role_words) else 5
    result = dict(candidate)
    result.update(
        {
            "match_score": round(min(100, score + location_score + role_score)),
            "matched_skills": matched,
            "missing_skills": [skill for skill in skills if skill not in matched],
            "evidence": [
                f"Public profile evidence matches: {', '.join(matched)}"
                if matched
                else "No requested skill evidence found in the public fields.",
                f"Location evidence: {candidate.get('location') or 'not listed'}",
            ],
            "confidence": (
                "High"
                if len(matched) == len(skills) and (candidate.get("location") or repositories)
                else "Medium"
                if matched
                else "Low"
            ),
            "confidence_reasons": [
                "All requested skills have public evidence."
                if skills and len(matched) == len(skills)
                else "Some requested skills have public evidence.",
                "GitHub repository evidence is available." if repositories else "No repository evidence was available.",
            ],
            "score_note": "Transparent evidence heuristic; verify experience at the source.",
        }
    )
    return result


def rank_candidates(session: AgentSession, limit: int = 8) -> str:
    """Rank sourced candidates only by observable public profile evidence."""
    ranked = [_rank(candidate, session.requirements) for candidate in session.candidates]
    ranked.sort(key=lambda candidate: candidate["match_score"], reverse=True)
    session.candidates = ranked[: max(1, min(limit, 15))]
    session.agent_steps.append(
        f"Ranked {len(ranked)} profiles into a shortlist of {len(session.candidates)}"
    )
    return json.dumps({"candidates": session.candidates}, ensure_ascii=False)


def get_shortlist(session: AgentSession, limit: int = 8) -> str:
    """Return the current shortlist for comparison or explanation."""
    return json.dumps({"candidates": session.candidates[:limit]}, ensure_ascii=False)


def draft_job_description(session: AgentSession) -> str:
    """Create a reviewable job description from the current hiring brief."""
    req = session.requirements
    role = req.get("role") or "Open role"
    skills = ", ".join(req.get("skills") or []) or "relevant skills"
    location = req.get("location") or "the agreed work location"
    years = f"{req.get('min_years', 0):g}+ years" if req.get("min_years", 0) else "relevant"
    draft = {
        "type": "job_description",
        "title": role,
        "content": (
            f"# {role}\n\n"
            f"## About the role\nJoin our team as a {role} and help us deliver measurable outcomes "
            f"with a collaborative, inclusive team in {location}.\n\n"
            f"## What you will do\n- Own well-scoped work from planning through delivery.\n"
            f"- Collaborate with product, design, and engineering partners.\n"
            f"- Communicate decisions clearly and improve the way the team works.\n\n"
            f"## What we are looking for\n- {years} of relevant experience.\n"
            f"- Practical experience with {skills}.\n"
            f"- Strong problem solving and written communication.\n\n"
            "## Hiring note\nThis draft is a starting point for recruiter review. Confirm compensation, "
            "location, accommodations, and legal wording before publishing."
        ),
    }
    session.last_draft = draft
    session.agent_steps.append("Drafted a job description for recruiter review")
    return json.dumps(draft, ensure_ascii=False)


def draft_candidate_outreach(session: AgentSession, candidate_name: str = "") -> str:
    """Create evidence-grounded outreach without sending it."""
    candidate = next(
        (item for item in session.candidates
         if (item.get("name") or item.get("username") or "").lower() == candidate_name.lower()),
        session.candidates[0] if session.candidates else {},
    )
    name = candidate.get("name") or candidate.get("username") or "there"
    role = session.requirements.get("role") or "an open role"
    evidence = ", ".join(candidate.get("matched_skills") or []) or "your public work"
    profile = candidate.get("profile_url") or candidate.get("url") or ""
    body = (
        f"Subject: Exploring {role}\n\n"
        f"Hi {name},\n\n"
        f"I’m reaching out about {role}. Your public work shows evidence of {evidence}, "
        "which looks relevant to the team’s needs. Would you be open to a short conversation "
        "to learn more about the role and share what you’re looking for?\n\n"
        f"Source reviewed: {profile or 'public profile evidence'}\n\nBest,\nRecruiting team"
    )
    draft = {"type": "outreach", "candidate": name, "content": body}
    session.last_draft = draft
    session.agent_steps.append("Drafted evidence-grounded outreach for recruiter review")
    return json.dumps(draft, ensure_ascii=False)


def generate_onboarding_checklist(session: AgentSession, role: str = "") -> str:
    """Return a lightweight onboarding checklist from local templates."""
    target = role or session.requirements.get("role") or "new team member"
    family = "engineering" if any(
        word in target.lower() for word in ("engineer", "developer", "technical", "software")
    ) else "general"
    templates = json.loads((DATA_DIR / "onboarding_templates.json").read_text())
    checklist = [
        {**item, "done": False} for item in templates.get(family, templates["general"])
    ]
    session.last_checklist = checklist
    session.agent_steps.append(f"Prepared a {len(checklist)}-item onboarding checklist")
    return json.dumps({"type": "onboarding", "role": target, "items": checklist}, ensure_ascii=False)


def query_hr_policy(session: AgentSession, question: str = "") -> str:
    """Answer common HR questions from the local policy knowledge base."""
    policies = json.loads((DATA_DIR / "hr_policies.json").read_text())
    query = question.lower()
    matches = [
        {"id": key, "title": item["title"], "answer": item["answer"]}
        for key, item in policies.items()
        if any(keyword in query for keyword in item["keywords"])
    ]
    if not matches:
        matches = [{"id": "general", "title": "HR policy lookup", "answer": (
            "I could not find a matching policy in the local HR knowledge base. "
            "Please confirm this with HR before acting."
        )}]
    session.last_policy_refs = matches
    session.agent_steps.append(f"Looked up {len(matches)} local HR policy reference(s)")
    return json.dumps({"type": "policy", "matches": matches}, ensure_ascii=False)


def _role_band_key(role: str) -> str:
    lowered = role.lower()
    if "front" in lowered or "react" in lowered:
        return "frontend_engineer"
    if "data" in lowered and "engineer" in lowered:
        return "data_engineer"
    if any(word in lowered for word in ("engineer", "developer", "software")):
        return "software_engineer"
    return "general"


def salary_band_guidance(session: AgentSession, role: str = "") -> str:
    """Return indicative local salary band guidance for recruiter and manager review."""
    target = role or session.requirements.get("role") or "Open role"
    bands = json.loads((DATA_DIR / "salary_bands.json").read_text())
    band = bands.get(_role_band_key(target), bands["general"])
    brief = {
        "type": "salary_guidance",
        "role": target,
        "band": band,
        "disclaimer": "Indicative band for planning only. Confirm with finance and local law before sharing with candidates.",
    }
    session.last_management_brief = brief
    session.agent_steps.append("Prepared indicative salary band guidance for review")
    return json.dumps(brief, ensure_ascii=False)


def pipeline_summary_for_management(session: AgentSession) -> str:
    """Summarize saved pipeline stages for hiring managers and HR leadership."""
    rows = list_candidates()
    by_stage: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        stage = row.get("pipeline_stage") or "Sourced"
        by_stage.setdefault(stage, []).append(row)
    top = sorted(rows, key=lambda item: item.get("match_score") or 0, reverse=True)[:5]
    brief = {
        "type": "pipeline_summary",
        "total": len(rows),
        "by_stage": {stage: len(items) for stage, items in by_stage.items()},
        "top_candidates": [
            {
                "name": item.get("name") or item.get("username"),
                "score": item.get("match_score"),
                "stage": item.get("pipeline_stage"),
            }
            for item in top
        ],
        "actions": [
            "Review shortlisted profiles against the live job brief.",
            "Confirm outreach drafts before any contact.",
            "Escalate compensation questions to finance with verified bands.",
        ],
    }
    session.last_management_brief = brief
    session.agent_steps.append(f"Summarized pipeline for management ({len(rows)} saved profiles)")
    return json.dumps(brief, ensure_ascii=False)


def generate_interview_pack(session: AgentSession, role: str = "", focus: str = "") -> str:
    """Create a structured interview question pack from the hiring brief."""
    target = role or session.requirements.get("role") or "the open role"
    skills = session.requirements.get("skills") or []
    focus_areas = [part.strip() for part in focus.split(",") if part.strip()] or skills[:4] or ["problem solving", "communication"]
    sections = {
        "screening": [
            f"Walk me through a recent project relevant to {target}.",
            "What team size and ownership model did you work in?",
        ],
        "technical": (
            [f"How have you applied {skill} in production?" for skill in focus_areas[:3]]
            or ["Describe a technical tradeoff you made and how you measured success."]
        ),
        "behavioral": [
            "Tell me about a time you disagreed with a stakeholder. What happened?",
            "How do you prioritize when deadlines and quality conflict?",
        ],
        "closing": [
            "What would you need to know about our team before accepting an offer?",
            "What timeline are you considering for your next move?",
        ],
    }
    pack = {
        "type": "interview_pack",
        "role": target,
        "focus_areas": focus_areas,
        "sections": sections,
        "note": "Questions are starting points. Avoid protected characteristics and verify answers against work samples.",
    }
    session.last_interview_pack = pack
    session.agent_steps.append("Generated an interview question pack for the hiring team")
    return json.dumps(pack, ensure_ascii=False)


def compare_candidates_brief(session: AgentSession, limit: int = 3) -> str:
    """Compare top shortlisted candidates with evidence-based pros and gaps."""
    pool = session.candidates or list_candidates()
    ranked = sorted(pool, key=lambda item: item.get("match_score") or 0, reverse=True)[: max(1, min(limit, 5))]
    comparisons = []
    for item in ranked:
        comparisons.append(
            {
                "name": item.get("name") or item.get("username"),
                "match_score": item.get("match_score"),
                "matched_skills": item.get("matched_skills") or [],
                "missing_skills": item.get("missing_skills") or [],
                "confidence": item.get("confidence") or "Unknown",
                "profile": item.get("profile_url") or item.get("url"),
                "pros": [
                    f"Public evidence for: {', '.join(item.get('matched_skills') or []) or 'limited skill signals'}",
                    f"Confidence label: {item.get('confidence') or 'verify manually'}",
                ],
                "gaps": item.get("missing_skills") or ["Verify seniority and scope from source profiles"],
            }
        )
    brief = {
        "type": "candidate_comparison",
        "count": len(comparisons),
        "candidates": comparisons,
        "disclaimer": "Comparison uses public evidence heuristics only; humans make hiring decisions.",
    }
    session.last_management_brief = brief
    session.agent_steps.append(f"Compared top {len(comparisons)} candidate(s) for committee review")
    return json.dumps(brief, ensure_ascii=False)
