from app.database.connection import init_db
from app.database.repository import ResearchRepository
from app.main import app
from app.schemas.research import ResearchStage, SessionStatus
from fastapi.testclient import TestClient


def test_summary_delta_events_ordered(tmp_path, monkeypatch):
    db = tmp_path / "ev.sqlite3"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    from app.config import get_settings

    get_settings.cache_clear()
    init_db(db)
    repo = ResearchRepository()
    sid = repo.create_session("Q")
    repo.append_event(sid, "summary_delta", {"text": "a", "iteration": 1})
    repo.append_event(sid, "summary_delta", {"text": "b", "iteration": 1})
    events = repo.list_events(sid, since_seq=0)
    assert [e["type"] for e in events] == ["summary_delta", "summary_delta"]
    assert events[0]["payload"]["text"] == "a"


def test_sse_response_headers(tmp_path, monkeypatch):
    db = tmp_path / "sse.sqlite3"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    from app.config import get_settings

    get_settings.cache_clear()
    init_db(db)
    repo = ResearchRepository()
    sid = repo.create_session("Q")
    repo.update_session(sid, status=SessionStatus.COMPLETE, stage=ResearchStage.COMPLETE)

    client = TestClient(app)
    with client.stream("GET", f"/api/research/{sid}/events", params={"since_seq": 0}) as resp:
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-cache"
        assert resp.headers.get("x-accel-buffering") == "no"
        lines = list(resp.iter_lines())
    assert any("stream_end" in (line or "") for line in lines)
