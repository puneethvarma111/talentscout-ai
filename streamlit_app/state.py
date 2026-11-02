import asyncio
import os
from typing import Any, Callable

import streamlit as st
from ollama import Client

from app.agent import run_agent
from app.session import AgentSession


def get_agent_session() -> AgentSession:
    if "agent_session" not in st.session_state:
        st.session_state.agent_session = AgentSession()
    return st.session_state.agent_session


def get_client() -> Client:
    return Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))


def execute_agent(
    message: str,
    on_step: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    session = get_agent_session()
    result = asyncio.run(
        run_agent(
            get_client(),
            os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
            session,
            message,
            on_step=on_step,
        )
    )
    st.session_state.last_result = result
    return result


def candidates() -> list[dict[str, Any]]:
    return get_agent_session().candidates
