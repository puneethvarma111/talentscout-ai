import json
import os
from typing import Any

from ollama import Client


def draft_outreach(candidate: dict[str, Any], role: str) -> str:
    """Draft a short outreach message using only the supplied public evidence."""
    evidence = json.dumps(
        {
            "name": candidate.get("name") or candidate.get("username"),
            "bio": candidate.get("bio") or candidate.get("snippet"),
            "matched_skills": candidate.get("matched_skills", []),
            "repositories": candidate.get("repositories", [])[:5],
            "profile_url": candidate.get("profile_url") or candidate.get("url"),
        },
        ensure_ascii=False,
    )
    response = Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434")).chat(
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
        messages=[
            {
                "role": "system",
                "content": "Write a respectful 3-sentence recruiting outreach draft. "
                "Use only facts in the evidence JSON. Do not claim employment, years, "
                "availability, or personal details not present. Return subject and body.",
            },
            {"role": "user", "content": f"Role: {role}\nEvidence JSON: {evidence}"},
        ],
        options={"temperature": 0.3},
    )
    return response.message.content or ""
