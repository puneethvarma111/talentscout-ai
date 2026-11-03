from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from app.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_TOOLS = {"web_search", "fetch_webpage_tool"}


def _hash_args(name: str, args: dict[str, Any]) -> str:
    payload = json.dumps({"name": name, "args": args}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class ExecutionLoop:
    def __init__(
        self,
        model,
        tools: list[BaseTool],
        *,
        max_rounds: int | None = None,
        max_tool_calls: int | None = None,
    ):
        settings = get_settings()
        self.model = model
        self.tools = {t.name: t for t in tools if t.name in ALLOWED_TOOLS}
        self.max_rounds = max_rounds or settings.max_tool_rounds
        self.max_tool_calls = max_tool_calls or settings.max_tool_calls
        self.tool_call_count = 0
        self.seen_hashes: set[str] = set()

    def _validate_args(self, name: str, args: dict[str, Any]) -> str | None:
        if name not in ALLOWED_TOOLS:
            return f"Tool {name} is not allowed"
        if name == "web_search":
            q = str(args.get("query", "")).strip()
            if len(q) < 2 or len(q) > 500:
                return "Invalid query length"
        if name == "fetch_webpage_tool":
            url = str(args.get("url", "")).strip()
            if not url.startswith("http"):
                return "Invalid URL"
        return None

    def _run_tool(self, name: str, args: dict[str, Any]) -> str:
        err = self._validate_args(name, args)
        if err:
            return f"Tool validation error: {err}"
        h = _hash_args(name, args)
        if h in self.seen_hashes:
            return "Duplicate tool call skipped."
        self.seen_hashes.add(h)
        if self.tool_call_count >= self.max_tool_calls:
            return "Maximum tool calls reached for this session."
        self.tool_call_count += 1
        tool = self.tools.get(name)
        if not tool:
            return f"Unknown tool: {name}"
        try:
            result = tool.invoke(args)
            return str(result)
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return f"Tool execution error: {exc}"

    def run(self, task: str, system: str = "You are a research assistant with web tools.") -> str:
        bound = self.model.bind_tools(list(self.tools.values()))
        messages: list = [SystemMessage(content=system), HumanMessage(content=task)]
        final = ""
        for _ in range(self.max_rounds):
            ai: AIMessage = bound.invoke(messages)
            if not ai.tool_calls:
                final = ai.content if isinstance(ai.content, str) else str(ai.content)
                break
            messages.append(ai)
            for call in ai.tool_calls:
                name = call["name"]
                args = call.get("args") or {}
                output = self._run_tool(name, args)
                messages.append(ToolMessage(content=output, tool_call_id=call["id"]))
        return final or "Research step completed without a final message."


def run_with_fallback(
    task: str,
    loop: ExecutionLoop,
    fallback: Callable[[], str],
) -> str:
    try:
        result = loop.run(task)
        if result and "Tool validation error" not in result and "Maximum tool calls" not in result:
            return result
    except Exception as exc:
        logger.warning("Tool loop failed, using fallback: %s", exc)
    return fallback()
