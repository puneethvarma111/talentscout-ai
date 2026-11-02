"""LangGraph supervisor pattern (Hub-and-Spoke) for HR recruiting workflows.

Mirrors the my-first-agent architecture: specialized workers, shared session state,
SQLite checkpoint memory, and MCP-backed sourcing on the recruiting worker only.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app import agent_tools
from app.mcp_tools import mcp_session
from app.session import AgentSession

ROOT = Path(__file__).resolve().parent.parent
MEMORY_DB = ROOT / "agent_memory.sqlite"
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next: str


class EmptyInput(BaseModel):
    pass


class RoleInput(BaseModel):
    role: str = Field(default="", description="Job title or role family")


class QuestionInput(BaseModel):
    question: str = Field(..., description="HR policy question")


class CandidateInput(BaseModel):
    candidate_name: str = Field(default="", description="Shortlisted candidate name or username")


class LimitInput(BaseModel):
    limit: int = Field(default=3, ge=1, le=5)


class FocusInput(BaseModel):
    role: str = Field(default="")
    focus: str = Field(default="", description="Comma-separated focus areas or skills")


class RequirementsInput(BaseModel):
    role: str = Field(default="")
    skills: list[str] = Field(default_factory=list)
    location: str = Field(default="")
    min_years: float = Field(default=0)
    max_years: float = Field(default=99)


def _run_async(coro):
    return asyncio.run(coro)


def _mcp_tool(name: str, description: str, schema: type[BaseModel]):
    def handler(**kwargs):
        async def call():
            async with mcp_session() as bridge:
                return await bridge.call_tool(name, kwargs)

        return _run_async(call())

    return StructuredTool.from_function(
        func=handler,
        name=name,
        description=description,
        args_schema=schema,
    )


class McpGitHubSearchInput(BaseModel):
    query: str = Field(..., description="GitHub user search query")
    per_page: int = Field(default=8, ge=1, le=15)


class McpWebSearchInput(BaseModel):
    query: str = Field(..., description="Web search query")
    max_results: int = Field(default=8, ge=1, le=10)


class McpReposInput(BaseModel):
    username: str = Field(..., description="GitHub username")
    limit: int = Field(default=8, ge=1, le=15)


def build_recruiting_tools(session_holder: dict[str, AgentSession]) -> list[StructuredTool]:
    session = session_holder["session"]

    def set_requirements(**kwargs):
        return agent_tools.set_job_requirements(session, **kwargs)

    def search():
        return _run_async(agent_tools.search_candidates(session))

    def rank(limit: int = 8):
        return agent_tools.rank_candidates(session, limit=limit)

    def shortlist(limit: int = 8):
        return agent_tools.get_shortlist(session, limit=limit)

    def outreach(candidate_name: str = ""):
        return agent_tools.draft_candidate_outreach(session, candidate_name=candidate_name)

    def compare(limit: int = 3):
        return agent_tools.compare_candidates_brief(session, limit=limit)

    return [
        StructuredTool.from_function(
            func=set_requirements,
            name="set_job_requirements",
            description="Save explicit job criteria before sourcing.",
            args_schema=RequirementsInput,
        ),
        StructuredTool.from_function(
            func=search,
            name="search_candidates",
            description="Search public GitHub/web sources using saved criteria.",
            args_schema=EmptyInput,
        ),
        StructuredTool.from_function(
            func=rank,
            name="rank_candidates",
            description="Rank sourced candidates by public evidence.",
            args_schema=LimitInput,
        ),
        StructuredTool.from_function(
            func=shortlist,
            name="get_shortlist",
            description="Return the current shortlist.",
            args_schema=LimitInput,
        ),
        StructuredTool.from_function(
            func=outreach,
            name="draft_candidate_outreach",
            description="Draft evidence-grounded outreach; never send automatically.",
            args_schema=CandidateInput,
        ),
        StructuredTool.from_function(
            func=compare,
            name="compare_candidates_brief",
            description="Compare top candidates for hiring committee review.",
            args_schema=LimitInput,
        ),
        _mcp_tool(
            "github_search_users",
            "Search public GitHub profiles for sourcing.",
            McpGitHubSearchInput,
        ),
        _mcp_tool(
            "public_web_search",
            "Search public web for portfolios and professional profiles.",
            McpWebSearchInput,
        ),
        _mcp_tool(
            "github_list_user_repos",
            "List public GitHub repos as technical evidence.",
            McpReposInput,
        ),
    ]


def build_hr_ops_tools(session_holder: dict[str, AgentSession]) -> list[StructuredTool]:
    session = session_holder["session"]

    return [
        StructuredTool.from_function(
            func=lambda: agent_tools.draft_job_description(session),
            name="draft_job_description",
            description="Draft a job description from the saved hiring brief.",
            args_schema=EmptyInput,
        ),
        StructuredTool.from_function(
            func=lambda role="": agent_tools.generate_onboarding_checklist(session, role=role),
            name="generate_onboarding_checklist",
            description="Create an onboarding checklist for a role.",
            args_schema=RoleInput,
        ),
        StructuredTool.from_function(
            func=lambda role="", focus="": agent_tools.generate_interview_pack(
                session, role=role, focus=focus
            ),
            name="generate_interview_pack",
            description="Generate structured interview questions for hiring managers.",
            args_schema=FocusInput,
        ),
        StructuredTool.from_function(
            func=lambda role="": agent_tools.salary_band_guidance(session, role=role),
            name="salary_band_guidance",
            description="Indicative salary band guidance for planning (not an offer).",
            args_schema=RoleInput,
        ),
    ]


def build_policy_tools(session_holder: dict[str, AgentSession]) -> list[StructuredTool]:
    session = session_holder["session"]

    return [
        StructuredTool.from_function(
            func=lambda question="": agent_tools.query_hr_policy(session, question=question),
            name="query_hr_policy",
            description="Answer leave, remote, holiday, or benefits questions from local policy KB.",
            args_schema=QuestionInput,
        ),
        StructuredTool.from_function(
            func=lambda: agent_tools.pipeline_summary_for_management(session),
            name="pipeline_summary_for_management",
            description="Summarize pipeline stages for HR leadership and hiring managers.",
            args_schema=EmptyInput,
        ),
    ]


def create_worker_node(name: str, tools: list[StructuredTool], system_prompt: str):
    llm = ChatOllama(model=DEFAULT_MODEL, temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    def node(state: AgentState):
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        result = llm_with_tools.invoke(messages)
        return {"messages": [result]}

    return node


def supervisor_node(state: AgentState):
    system_prompt = (
        "You are the TalentScout HR Supervisor coordinating three workers:\n"
        "1. Recruiting_Agent — sourcing, ranking, shortlists, outreach drafts, candidate comparison, GitHub/web search.\n"
        "2. HR_Ops_Agent — job descriptions, onboarding checklists, interview packs, salary band guidance.\n"
        "3. Policy_Agent — local HR policy answers and management pipeline summaries.\n\n"
        "Route one worker at a time. Choose FINISH when the user's request is answered or you need clarification.\n"
        "Never invent candidate data. Remind humans to verify public evidence and approve drafts before sending."
    )
    llm = ChatOllama(model=DEFAULT_MODEL, temperature=0)
    prompt = (
        "Who should act next? Reply with JSON only: {\"next\": \"Recruiting_Agent\" | "
        "\"HR_Ops_Agent\" | \"Policy_Agent\" | \"FINISH\"}."
    )
    messages = [SystemMessage(content=system_prompt)] + state["messages"] + [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    try:
        content = response.content if isinstance(response.content, str) else str(response.content)
        start, end = content.find("{"), content.rfind("}")
        decision = json.loads(content[start : end + 1])
        next_step = decision.get("next", "FINISH")
    except (json.JSONDecodeError, ValueError):
        next_step = "FINISH"
    if next_step not in {"Recruiting_Agent", "HR_Ops_Agent", "Policy_Agent", "FINISH"}:
        next_step = "FINISH"
    return {"next": next_step}


def should_continue_to_tools(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "supervisor"


def build_supervisor_app(session: AgentSession):
    holder = {"session": session}
    recruiting_tools = build_recruiting_tools(holder)
    hr_tools = build_hr_ops_tools(holder)
    policy_tools = build_policy_tools(holder)

    recruiting_node = create_worker_node(
        "Recruiting_Agent",
        recruiting_tools,
        "You are a Recruiting Specialist. Source and rank public candidates, draft outreach, "
        "and compare shortlists. Do not answer policy questions or write full job descriptions.",
    )
    hr_node = create_worker_node(
        "HR_Ops_Agent",
        hr_tools,
        "You are an HR Operations Specialist. Draft job descriptions, onboarding, interview packs, "
        "and salary guidance. Do not source candidates or send outreach.",
    )
    policy_node = create_worker_node(
        "Policy_Agent",
        policy_tools,
        "You are a People Policy Specialist. Answer from the local policy knowledge base and "
        "summarize the hiring pipeline for managers. Do not source candidates.",
    )

    workflow = StateGraph(AgentState)
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("Recruiting_Agent", recruiting_node)
    workflow.add_node("HR_Ops_Agent", hr_node)
    workflow.add_node("Policy_Agent", policy_node)
    workflow.add_node("Recruiting_Tools", ToolNode(recruiting_tools))
    workflow.add_node("HR_Tools", ToolNode(hr_tools))
    workflow.add_node("Policy_Tools", ToolNode(policy_tools))

    workflow.add_edge(START, "Supervisor")
    workflow.add_conditional_edges(
        "Supervisor",
        lambda state: state["next"],
        {
            "Recruiting_Agent": "Recruiting_Agent",
            "HR_Ops_Agent": "HR_Ops_Agent",
            "Policy_Agent": "Policy_Agent",
            "FINISH": END,
        },
    )

    for worker, tool_node in (
        ("Recruiting_Agent", "Recruiting_Tools"),
        ("HR_Ops_Agent", "HR_Tools"),
        ("Policy_Agent", "Policy_Tools"),
    ):
        workflow.add_conditional_edges(
            worker,
            should_continue_to_tools,
            {"tools": tool_node, "supervisor": "Supervisor"},
        )
        workflow.add_edge(tool_node, worker)

    conn = sqlite3.connect(MEMORY_DB, check_same_thread=False)
    memory = SqliteSaver(conn)
    return workflow.compile(checkpointer=memory)


def run_supervisor(
    session: AgentSession,
    user_message: str,
    thread_id: str,
    recursion_limit: int = 18,
) -> dict:
    app = build_supervisor_app(session)
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": recursion_limit,
    }
    session.reset_steps()
    session.messages.append({"role": "user", "content": user_message})
    session.agent_steps.append("Supervisor workflow started")

    final_text = ""
    worker_trace: list[str] = []

    for event in app.stream(
        {"messages": [HumanMessage(content=user_message)], "next": "FINISH"},
        config,
        stream_mode="values",
    ):
        messages = event.get("messages") or []
        if not messages:
            continue
        last = messages[-1]
        if isinstance(last, AIMessage):
            if last.tool_calls:
                for call in last.tool_calls:
                    worker_trace.append(f"Tool: {call.get('name', 'unknown')}")
                    session.agent_steps.append(f"Worker tool {call.get('name', 'unknown')}")
            if last.content and not last.tool_calls:
                final_text = last.content if isinstance(last.content, str) else str(last.content)

    if not final_text:
        final_text = "I could not complete the supervisor workflow. Try a more specific HR or recruiting request."

    session.messages.append({"role": "assistant", "content": final_text})
    return {
        "reply": final_text,
        "steps": session.agent_steps,
        "worker_trace": worker_trace,
        "requirements": session.requirements,
        "candidates": session.candidates,
        "draft": session.last_draft,
        "checklist": session.last_checklist,
        "policy_refs": session.last_policy_refs,
        "management_brief": session.last_management_brief,
        "interview_pack": session.last_interview_pack,
        "mode": "supervisor",
        "needs_confirmation": not bool(
            session.requirements.get("role") or session.requirements.get("skills")
        ),
    }
