from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def get_chat_model(temperature: float = 0.1) -> ChatOllama:
    s = get_settings()
    return ChatOllama(
        model=s.ollama_model,
        base_url=s.ollama_base_url,
        temperature=temperature,
        num_ctx=s.effective_ollama_num_ctx,
        num_predict=s.effective_ollama_num_predict,
    )


def check_ollama_health() -> dict[str, Any]:
    s = get_settings()
    try:
        r = httpx.get(f"{s.ollama_base_url.rstrip('/')}/api/tags", timeout=5.0)
        r.raise_for_status()
        models = [m.get("name", "") for m in r.json().get("models", [])]
        model_ok = any(s.ollama_model.split(":")[0] in m for m in models) or s.ollama_model in models
        return {
            "ok": True,
            "ollama_reachable": True,
            "model": s.ollama_model,
            "model_available": model_ok,
            "models": models[:10],
        }
    except Exception as exc:
        return {
            "ok": False,
            "ollama_reachable": False,
            "model": s.ollama_model,
            "error": str(exc),
        }


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return json.loads(text)
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        return json.loads(fence.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("No JSON found in model output")


def invoke_structured(
    model: ChatOllama,
    schema: type[T],
    system: str,
    user: str,
    *,
    retries: int | None = None,
) -> T:
    """Structured output with with_structured_output fallback to JSON parsing."""
    if retries is None:
        retries = get_settings().effective_structured_output_retries
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            structured = model.with_structured_output(schema)
            result = structured.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            if isinstance(result, schema):
                return result
            return schema.model_validate(result)
        except Exception as exc:
            last_err = exc
            logger.debug("structured_output attempt %s failed: %s", attempt, exc)
    prompt = (
        f"{user}\n\nRespond with ONLY valid JSON matching this schema (no markdown):\n"
        f"{json.dumps(schema.model_json_schema(), indent=2)}"
    )
    for attempt in range(retries + 1):
        try:
            msg = model.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            data = _extract_json(content)
            return schema.model_validate(data)
        except Exception as exc:
            last_err = exc
            logger.warning("JSON fallback attempt %s failed: %s", attempt, exc)
    raise RuntimeError(f"Failed to parse structured output: {last_err}") from last_err
