"""Pluggable LLM providers. LLM_PROVIDER = auto | ollama | openai | mock."""
from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

import httpx


def provider_name() -> str:
    p = os.getenv("LLM_PROVIDER", "auto").lower()
    if p != "auto":
        return p
    try:
        httpx.get(f"{os.getenv('OLLAMA_HOST', 'http://localhost:11434')}/api/tags", timeout=1.5).raise_for_status()
        return "ollama"
    except Exception:
        return "openai" if os.getenv("OPENAI_API_KEY") else "mock"


def model_name(provider: str) -> str:
    if provider == "ollama":
        return os.getenv("COPILOT_MODEL") or os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return "rule-based mock"


async def stream_chat(provider: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    """Yields {"token": str} chunks and finally {"tool_calls": [...], "content": str}."""
    if provider == "ollama":
        from ollama import AsyncClient

        client = AsyncClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
        kwargs: dict[str, Any] = dict(model=model_name("ollama"), messages=messages, tools=tools, stream=True, options={"temperature": 0.1})
        try:
            stream = await client.chat(**kwargs, think=False)
        except TypeError:
            stream = await client.chat(**kwargs)
        content, calls = "", []
        async for chunk in stream:
            msg = chunk.message
            if msg.content:
                content += msg.content
                yield {"token": msg.content}
            for tc in msg.tool_calls or []:
                calls.append({"name": tc.function.name, "arguments": dict(tc.function.arguments or {})})
        yield {"tool_calls": calls, "content": content}
        return

    if provider == "openai":
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}"},
                json={"model": model_name("openai"), "messages": _to_openai(messages), "tools": tools, "temperature": 0.1},
            )
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
        content = msg.get("content") or ""
        for i in range(0, len(content), 24):
            yield {"token": content[i:i + 24]}
        calls = [{"name": c["function"]["name"], "arguments": json.loads(c["function"].get("arguments") or "{}"), "id": c.get("id")} for c in msg.get("tool_calls") or []]
        yield {"tool_calls": calls, "content": content}
        return
    raise ValueError(f"Unknown LLM_PROVIDER {provider}")


def _to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        if m["role"] == "assistant" and m.get("tool_calls"):
            out.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": [
                {"id": tc.get("id") or f"call_{i}", "type": "function", "function": {"name": tc["function"]["name"], "arguments": json.dumps(tc["function"]["arguments"])}}
                for i, tc in enumerate(m["tool_calls"])]})
        elif m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m.get("tool_call_id", "call_0"), "content": m["content"]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out
