from __future__ import annotations

from app.agent.execution_loop import ExecutionLoop, run_with_fallback
from app.agent.gap_analyzer import analyze_gaps
from app.agent.planner import create_research_plan
from app.agent.query_generator import generate_search_queries
from app.llm.ollama_client import get_chat_model
from app.tools.webpage_tool import fetch_webpage_tool, web_search


class ResearchAgent:
    """Thin facade over planner/query tools and optional execution loop."""

    def __init__(self):
        self.model = get_chat_model()
        self.loop = ExecutionLoop(self.model, [web_search, fetch_webpage_tool])

    def plan(self, question: str):
        return create_research_plan(question)

    def queries(self, plan, gap=None):
        return generate_search_queries(plan, gap)

    def gaps(self, plan, findings, iteration: int):
        return analyze_gaps(plan, findings, iteration)

    def optional_tool_research(self, task: str, fallback_fn):
        return run_with_fallback(task, self.loop, fallback_fn)
