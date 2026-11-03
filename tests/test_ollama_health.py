from unittest.mock import patch

from app.llm.ollama_client import check_ollama_health


def test_ollama_health_failure():
    with patch("app.llm.ollama_client.httpx.get", side_effect=ConnectionError("down")):
        result = check_ollama_health()
    assert result["ok"] is False
    assert result["ollama_reachable"] is False
