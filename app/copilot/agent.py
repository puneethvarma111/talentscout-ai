"""Bounded tool-calling loop that yields UI events."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

from app.copilot import hrms, llm, mock
from app.copilot.tools import TOOLS, CopilotSession, run_tool, tool_schemas

MAX_ROUNDS = 5

SYSTEM = """You are Swiftlyy HR Copilot, an assistant for employees, managers and HR teams.
Today is {today}. Current user: {actor} (role: {persona}).
Rules:
- Use tools for ANY fact about people, leave, attendance, policies or resumes. Never invent numbers, names, dates or policy text.
- If a tool returns an error or nothing, say so plainly and suggest the next step. Do not guess.
- Policy answers must quote/cite the citation strings returned by search_hr_policy, e.g. [Company policy: Annual leave §1].
- Respect role limits: if access is denied, explain it politely; do not try other tools to get around it.
- Offer letters and anything that would be sent are drafts that need human approval. Never claim something was sent.
- Do not use or infer protected characteristics (gender, religion, caste, age, health, marital status) in any judgement.
- Keep answers short and scannable: a one-line answer first, then bullets. Tables are shown to the user separately, so summarise rather than repeat them.
Uploaded files this session: {files}
"""


def _event(kind: str, **data: Any) -> dict[str, Any]:
    return {"type": kind, **data}


async def run(session: CopilotSession, message: str) -> AsyncIterator[dict[str, Any]]:
    provider = llm.provider_name()
    yield _event("meta", provider=provider, model=llm.model_name(provider), persona=session.actor, data_source=hrms.data_source())
    session.messages.append({"role": "user", "content": message})
    if provider == "mock":
        async for ev in _run_mock(session, message):
            yield ev
        return
    try:
        async for ev in _run_llm(session, provider):
            yield ev
    except Exception as exc:  # provider down mid-turn → degrade gracefully
        yield _event("notice", text=f"The {provider} model failed ({type(exc).__name__}). Answered in offline mode instead.")
        async for ev in _run_mock(session, message):
            yield ev


async def _run_tool_events(session: CopilotSession, name: str, args: dict[str, Any], step_id: str) -> AsyncIterator[dict[str, Any]]:
    label = TOOLS.get(name, (None, None, name))[2]
    yield _event("step", id=step_id, status="running", tool=name, label=label, args=args)
    t0 = time.perf_counter()
    res = await asyncio.to_thread(run_tool, session, name, args)
    yield _event("step", id=step_id, status="done" if res.get("ok") else "error", tool=name, label=label, args=args,
                 summary=res.get("summary"), ms=round((time.perf_counter() - t0) * 1000))
    if res.get("artifact"):
        yield _event("artifact", artifact=res["artifact"])
    if res.get("approval"):
        yield _event("approval", approval=res["approval"])
    yield _event("_result", result=res)


async def _run_mock(session: CopilotSession, message: str) -> AsyncIterator[dict[str, Any]]:
    plan = mock.route(message, has_resume=any(d.kind == "resume" for d in session.docs))
    results = []
    for i, (name, args) in enumerate(plan):
        async for ev in _run_tool_events(session, name, args, f"s{i}"):
            if ev["type"] == "_result":
                results.append((name, ev["result"]))
            else:
                yield ev
    text = mock.answer(results)
    for i in range(0, len(text), 12):
        yield _event("token", text=text[i:i + 12])
        await asyncio.sleep(0.008)
    session.messages.append({"role": "assistant", "content": text})
    yield _event("done", text=text)


async def _run_llm(session: CopilotSession, provider: str) -> AsyncIterator[dict[str, Any]]:
    files = ", ".join(f"{d.name} ({d.kind})" for d in session.docs) or "none"
    system = SYSTEM.format(today=hrms.as_of(), actor=session.actor["label"], persona=session.actor["persona"], files=files)
    convo: list[dict[str, Any]] = [{"role": "system", "content": system}] + session.messages[-12:]
    final = ""
    for rnd in range(MAX_ROUNDS):
        calls, content = [], ""
        async for chunk in llm.stream_chat(provider, convo, tool_schemas()):
            if "token" in chunk:
                yield _event("token", text=chunk["token"])
            else:
                calls, content = chunk["tool_calls"], chunk["content"]
        if not calls:
            final = content
            break
        if content:
            yield _event("reset_text")  # pre-tool chatter is replaced by the final answer
        convo.append({"role": "assistant", "content": content, "tool_calls": [{**({"id": c["id"]} if c.get("id") else {}), "function": {"name": c["name"], "arguments": c["arguments"]}} for c in calls]})
        for j, c in enumerate(calls):
            async for ev in _run_tool_events(session, c["name"], c["arguments"], f"r{rnd}-{j}"):
                if ev["type"] == "_result":
                    r = ev["result"]
                    payload = json.dumps({"summary": r.get("summary"), "data": r.get("data")}, ensure_ascii=False, default=str)[:6000]
                    convo.append({"role": "tool", "content": payload, "tool_call_id": c.get("id") or f"call_{j}", "tool_name": c["name"]})
                else:
                    yield ev
    else:
        final = final or "I stopped after several tool steps. Please narrow the question."
        yield _event("token", text=final)
    session.messages.append({"role": "assistant", "content": final})
    yield _event("done", text=final)
