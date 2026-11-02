from dataclasses import dataclass, field
from typing import Any


DEFAULT_REQUIREMENTS: dict[str, Any] = {
    "role": "",
    "skills": [],
    "location": "",
    "min_years": 0,
    "max_years": 99,
    "salary_min_lpa": None,
    "salary_max_lpa": None,
}


@dataclass
class AgentSession:
    requirements: dict[str, Any] = field(
        default_factory=lambda: DEFAULT_REQUIREMENTS.copy()
    )
    messages: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    enrichment: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    agent_steps: list[str] = field(default_factory=list)
    last_draft: dict[str, Any] | None = None
    last_checklist: list[dict[str, Any]] = field(default_factory=list)
    last_policy_refs: list[dict[str, Any]] = field(default_factory=list)
    last_management_brief: dict[str, Any] | None = None
    last_interview_pack: dict[str, Any] | None = None

    def reset_steps(self) -> None:
        self.agent_steps = []


_sessions: dict[str, AgentSession] = {}


def get_session(session_id: str) -> AgentSession:
    if session_id not in _sessions:
        _sessions[session_id] = AgentSession()
    return _sessions[session_id]
