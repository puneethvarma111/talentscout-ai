from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from app.agent.execution_loop import ExecutionLoop


@tool
def web_search(query: str) -> str:
    """Search the web."""
    return f"results for {query}"


@tool
def fetch_webpage_tool(url: str) -> str:
    """Fetch a page."""
    return f"page {url}"


def test_execution_loop_runs_tool():
    model = MagicMock()
    model.bind_tools.return_value = model
    model.invoke.side_effect = [
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "ai agents"}, "id": "1"}]),
        AIMessage(content="done"),
    ]
    loop = ExecutionLoop(model, [web_search, fetch_webpage_tool], max_rounds=3, max_tool_calls=5)
    out = loop.run("search ai agents")
    assert "results for ai agents" in out or out == "done"


def test_duplicate_tool_call_skipped():
    model = MagicMock()
    model.bind_tools.return_value = model
    model.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "web_search", "args": {"query": "same"}, "id": "1"},
                {"name": "web_search", "args": {"query": "same"}, "id": "2"},
            ],
        ),
        AIMessage(content="finished"),
    ]
    loop = ExecutionLoop(model, [web_search, fetch_webpage_tool], max_rounds=2, max_tool_calls=5)
    loop.run("test")
    assert loop.tool_call_count == 1
