import json
from typing import Any, Callable

from ollama import Client

from app.agent_tools import (
    compare_candidates_brief,
    draft_candidate_outreach,
    draft_job_description,
    generate_interview_pack,
    generate_onboarding_checklist,
    get_shortlist,
    pipeline_summary_for_management,
    rank_candidates,
    query_hr_policy,
    salary_band_guidance,
    search_candidates,
    set_job_requirements,
)
from app.mcp_tools import mcp_session
from app.session import AgentSession


SYSTEM_PROMPT = """You are TalentScout HR, a careful recruiting and HR operations assistant.
Work in this order when appropriate: intake explicit criteria, source public
profiles, rank by observable evidence, then explain and refine.
For HR operations, use the job description, outreach, onboarding, and policy
tools. Use tools instead of asking the recruiter to click buttons. Ask one concise
clarifying question when a role is too vague to search. Never invent experience,
salary, seniority, or contact details. Never use protected characteristics or
their proxies. Do not make a hiring decision. Always mention that public evidence
must be verified and cite source links when discussing candidates.
Outreach and job descriptions are drafts for human review only; never send or publish them.
Policy answers come only from the local policy knowledge base and should be confirmed with HR.
You are in a bounded tool loop. Make a short internal plan, call the necessary
tools, then provide a concise recruiter-facing summary. For a follow-up, reuse
the current session and update or rerank it rather than starting over.
"""


APP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_job_requirements",
            "description": "Save explicit job criteria. Call this before sourcing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                    "location": {"type": "string"},
                    "min_years": {"type": "number"},
                    "max_years": {"type": "number"},
                    "salary_min_lpa": {"type": ["number", "null"]},
                    "salary_max_lpa": {"type": ["number", "null"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_candidates",
            "description": "Search public GitHub and web sources using saved criteria.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank_candidates",
            "description": "Rank sourced candidates by transparent public evidence.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 15}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shortlist",
            "description": "Return the current candidate shortlist.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 15}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_job_description",
            "description": "Draft a job description from the saved hiring brief for review.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_candidate_outreach",
            "description": "Draft, but never send, outreach grounded in a shortlisted candidate's public evidence.",
            "parameters": {
                "type": "object",
                "properties": {"candidate_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_onboarding_checklist",
            "description": "Create an onboarding checklist for a role.",
            "parameters": {"type": "object", "properties": {"role": {"type": "string"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_hr_policy",
            "description": "Answer a leave, remote work, holiday, or benefits question from the local HR policy knowledge base.",
            "parameters": {"type": "object", "properties": {"question": {"type": "string"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_interview_pack",
            "description": "Generate structured interview questions for hiring managers from the current brief.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "focus": {"type": "string", "description": "Comma-separated skills or themes"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "salary_band_guidance",
            "description": "Return indicative salary band guidance for planning (not a job offer).",
            "parameters": {"type": "object", "properties": {"role": {"type": "string"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_summary_for_management",
            "description": "Summarize saved pipeline stages for HR leadership and hiring managers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_candidates_brief",
            "description": "Compare top candidates with evidence-based pros and gaps for committee review.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 5}},
            },
        },
    },
]


def _dump_message(message: Any) -> dict[str, Any]:
    if hasattr(message, "model_dump"):
        data = message.model_dump(exclude_none=True)
    elif isinstance(message, dict):
        data = message
    else:
        data = {"role": "assistant", "content": getattr(message, "content", "")}
    return data


def _call_data(call: Any) -> tuple[str, dict[str, Any]]:
    function = call.get("function", {}) if isinstance(call, dict) else call.function
    if isinstance(function, dict):
        name = function.get("name", "")
        arguments = function.get("arguments", {})
    else:
        name = function.name
        arguments = function.arguments
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    return name, arguments or {}


async def run_agent(
    client: Client,
    model: str,
    session: AgentSession,
    user_message: str,
    on_step: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    def step(message: str) -> None:
        session.agent_steps.append(message)
        if on_step:
            on_step(message)

    session.reset_steps()
    session.messages.append({"role": "user", "content": user_message})
    async with mcp_session() as bridge:
        tools = APP_TOOLS + await bridge.list_tools()
        for _ in range(10):
            response = client.chat(
                model=model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, *session.messages],
                tools=tools,
                think=True,
                options={"temperature": 0.2},
            )
            assistant = _dump_message(response.message)
            session.messages.append(assistant)
            calls = assistant.get("tool_calls") or []
            if not calls:
                break
            for call in calls:
                name, arguments = _call_data(call)
                step(f"Agent called {name}")
                if name == "set_job_requirements":
                    result = set_job_requirements(session, **arguments)
                elif name == "search_candidates":
                    result = await search_candidates(session)
                elif name == "rank_candidates":
                    result = rank_candidates(session, **arguments)
                elif name == "get_shortlist":
                    result = get_shortlist(session, **arguments)
                elif name == "draft_job_description":
                    result = draft_job_description(session)
                elif name == "draft_candidate_outreach":
                    result = draft_candidate_outreach(session, **arguments)
                elif name == "generate_onboarding_checklist":
                    result = generate_onboarding_checklist(session, **arguments)
                elif name == "query_hr_policy":
                    result = query_hr_policy(session, **arguments)
                elif name == "generate_interview_pack":
                    result = generate_interview_pack(session, **arguments)
                elif name == "salary_band_guidance":
                    result = salary_band_guidance(session, **arguments)
                elif name == "pipeline_summary_for_management":
                    result = pipeline_summary_for_management(session)
                elif name == "compare_candidates_brief":
                    result = compare_candidates_brief(session, **arguments)
                else:
                    try:
                        result = await bridge.call_tool(name, arguments)
                    except Exception as exc:
                        result = {"error": f"{name} failed: {exc}"}
                session.messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": result if isinstance(result, str) else json.dumps(result),
                    }
                )

    reply = assistant.get("content") or "I could not complete that workflow."
    return {
        "reply": reply,
        "steps": session.agent_steps,
        "requirements": session.requirements,
        "candidates": session.candidates,
        "draft": session.last_draft,
        "checklist": session.last_checklist,
        "policy_refs": session.last_policy_refs,
        "management_brief": session.last_management_brief,
        "interview_pack": session.last_interview_pack,
        "needs_confirmation": not bool(
            session.requirements.get("role") or session.requirements.get("skills")
        ),
    }
