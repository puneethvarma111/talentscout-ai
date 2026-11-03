"""Local Research AI — ChatGPT-inspired dark research workspace."""

from __future__ import annotations

import json
import os
import queue
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

from theme import inject_css

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

SUGGESTIONS = [
    "Compare open-source AI agent frameworks for local deployment",
    "ChatGPT-like UI patterns for conversational research apps",
    "Best practices for chatbot UX: threading, loading states, accessibility",
    "Local LLM stack: Ollama vs LM Studio for research agents",
]

st.set_page_config(
    page_title="Local Research AI",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


def _init_state() -> None:
    defaults = {
        "messages": [],
        "event_log": [],
        "last_seq": 0,
        "watching": False,
        "active_session": None,
        "pending_prompt": None,
        "progress_text": "",
        "streaming_summary": "",
        "activity_line": "",
        "sse_queue": None,
        "sse_stop": None,
        "sse_consumer_session": None,
        "use_poll_fallback": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


def reset_session_tracking() -> None:
    stop_sse_consumer()
    st.session_state.event_log = []
    st.session_state.last_seq = 0
    st.session_state.watching = True
    st.session_state.progress_text = ""
    st.session_state.streaming_summary = ""
    st.session_state.activity_line = ""
    st.session_state.use_poll_fallback = False
    if st.session_state.active_session:
        start_sse_consumer(st.session_state.active_session)


def stop_sse_consumer() -> None:
    stop: threading.Event | None = st.session_state.get("sse_stop")
    if stop is not None:
        stop.set()
    st.session_state.sse_consumer_session = None


def _sse_reader(session_id: str, since_seq: int, out_q: queue.Queue, stop: threading.Event) -> None:
    url = f"{API_BASE}/api/research/{session_id}/events"
    try:
        with httpx.stream(
            "GET",
            url,
            params={"since_seq": since_seq},
            timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
        ) as response:
            response.raise_for_status()
            buf = ""
            for chunk in response.iter_text():
                if stop.is_set():
                    break
                buf += chunk
                while "\n\n" in buf:
                    block, buf = buf.split("\n\n", 1)
                    for line in block.splitlines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            out_q.put(json.loads(line[6:]))
                        except json.JSONDecodeError:
                            continue
    except Exception:
        out_q.put({"type": "_sse_error"})


def start_sse_consumer(session_id: str) -> None:
    stop_sse_consumer()
    st.session_state.sse_queue = queue.Queue()
    st.session_state.sse_stop = threading.Event()
    st.session_state.sse_consumer_session = session_id
    since = st.session_state.last_seq
    thread = threading.Thread(
        target=_sse_reader,
        args=(session_id, since, st.session_state.sse_queue, st.session_state.sse_stop),
        daemon=True,
        name=f"sse-{session_id[:8]}",
    )
    thread.start()


def apply_research_event(ev: dict) -> None:
    if ev.get("type") == "_sse_error":
        st.session_state.use_poll_fallback = True
        return
    if ev.get("type") == "stream_end":
        return
    if "seq" in ev:
        st.session_state.event_log.append(ev)
        st.session_state.last_seq = max(st.session_state.last_seq, ev.get("seq", 0))
    ev_type = ev.get("type")
    payload = ev.get("payload") or {}
    if ev_type == "summary_delta":
        st.session_state.streaming_summary += payload.get("text") or ""
    elif ev_type == "activity":
        detail = (payload.get("detail") or "").strip()
        label = payload.get("label") or "Working"
        st.session_state.activity_line = f"{label} · {detail}" if detail else label
    elif ev_type == "stage_changed":
        label = payload.get("label") or payload.get("stage") or "Working"
        st.session_state.activity_line = str(label)
    elif ev_type == "queries_generated":
        qs = payload.get("queries") or []
        st.session_state.activity_line = f"Searching · {len(qs)} queries"


def new_chat() -> None:
    stop_sse_consumer()
    st.session_state.messages = []
    st.session_state.active_session = None
    st.session_state.watching = False
    st.session_state.event_log = []
    st.session_state.last_seq = 0
    st.session_state.progress_text = ""
    st.session_state.streaming_summary = ""
    st.session_state.activity_line = ""
    st.session_state.use_poll_fallback = False


def api_get_json(path: str, *, timeout: float = 60.0, params: dict | None = None):
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=timeout, params=params)
        r.raise_for_status()
        return r.json()
    except httpx.ReadTimeout:
        return None
    except httpx.HTTPError:
        return None


def probe_ollama_direct() -> dict:
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
        ok = OLLAMA_MODEL in names or any(OLLAMA_MODEL.split(":")[0] in n for n in names)
        return {"ollama_reachable": True, "model": OLLAMA_MODEL, "model_available": ok}
    except Exception as exc:
        return {"ollama_reachable": False, "model": OLLAMA_MODEL, "error": str(exc)}


@st.cache_data(ttl=10)
def fetch_api_health():
    try:
        r = httpx.get(f"{API_BASE}/api/health", timeout=5)
        r.raise_for_status()
        return {"online": True, "data": r.json()}
    except Exception as exc:
        return {"online": False, "error": str(exc)}


def format_event_line(ev: dict) -> str:
    payload = ev.get("payload") or {}
    label = payload.get("label") or ev.get("type", "event")
    extra = ""
    if ev.get("type") == "queries_generated":
        qs = payload.get("queries") or []
        if qs:
            extra = f" — {qs[0][:60]}"
    if ev.get("type") == "reflection_done":
        fq = payload.get("follow_up_query") or ""
        if fq:
            extra = f" — next: {fq[:50]}"
    return f"{label}{extra}"


def build_progress_markdown(detail: dict | None) -> str:
    lines = []
    if detail:
        lines.append(
            f"**Stage:** `{detail.get('stage')}` · **Iteration:** {detail.get('iteration', 0)} · "
            f"**Sources:** {detail.get('sources_discovered', 0)} / "
            f"{detail.get('sources_extracted', 0)} extracted · "
            f"**Findings:** {detail.get('findings_count', 0)}"
        )
    elif st.session_state.watching:
        lines.append("_Still working — waiting for API status…_")
    for ev in st.session_state.event_log[-12:]:
        lines.append(f"- {format_event_line(ev)}")
    return "\n".join(lines) if lines else "_Starting research…_"


def extract_executive_summary(report_md: str) -> str:
    if not report_md:
        return ""
    m = re.search(
        r"## 1\. Executive Summary\s*\n(.*?)(?=\n## 2\.|\Z)",
        report_md,
        re.DOTALL,
    )
    return m.group(1).strip() if m else report_md[:2000]


def history_group(created_at: str) -> str:
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if dt.date() == now.date():
            return "Today"
        if (now.date() - dt.date()).days == 1:
            return "Yesterday"
        return "Older"
    except Exception:
        return "Older"


def start_research(question: str) -> None:
    st.session_state.messages.append({"role": "user", "kind": "question", "content": question})
    resp = httpx.post(f"{API_BASE}/api/research", json={"question": question.strip()}, timeout=30)
    resp.raise_for_status()
    sid = resp.json()["session_id"]
    st.session_state.active_session = sid
    reset_session_tracking()
    st.session_state.messages.append(
        {
            "role": "assistant",
            "kind": "progress",
            "content": "Research started. Gathering sources…",
            "session_id": sid,
        }
    )


def load_history_session(session_id: str, question: str, status: str) -> None:
    st.session_state.active_session = session_id
    st.session_state.messages = [
        {"role": "user", "kind": "question", "content": question},
        {
            "role": "assistant",
            "kind": "progress" if status == "running" else "report",
            "content": "Loaded from history.",
            "session_id": session_id,
        },
    ]
    st.session_state.event_log = []
    st.session_state.last_seq = 0
    st.session_state.watching = status == "running"
    st.session_state.progress_text = ""
    st.session_state.streaming_summary = ""
    st.session_state.activity_line = ""
    if status == "running":
        start_sse_consumer(session_id)


def render_report_tabs(session_id: str, detail: dict) -> None:
    report_resp = httpx.get(f"{API_BASE}/api/research/{session_id}/report", timeout=30)
    if report_resp.status_code != 200:
        st.warning("Report not available yet.")
        return
    data = report_resp.json()
    md = data.get("markdown") or ""
    refs = data.get("references") or []
    summary = (detail.get("running_summary_md") or "").strip() or extract_executive_summary(md)

    tab_sum, tab_full, tab_src, tab_exp = st.tabs(["Summary", "Full report", "Sources", "Export"])
    with tab_sum:
        if summary:
            st.markdown(summary)
        else:
            st.caption("No summary available.")
    with tab_full:
        st.markdown(md)
    with tab_src:
        st.caption(
            f"{detail.get('sources_discovered', 0)} discovered · "
            f"{detail.get('sources_extracted', 0)} extracted · "
            f"{detail.get('findings_count', 0)} findings"
        )
        for ref in refs:
            st.markdown(f"- [{ref.get('title', ref['url'])}]({ref['url']})")
    with tab_exp:
        st.download_button(
            "Download Markdown",
            md,
            file_name=f"research-{session_id[:8]}.md",
            use_container_width=True,
        )
        pdf = httpx.get(f"{API_BASE}/api/research/{session_id}/report.pdf", timeout=60)
        if pdf.status_code == 200:
            st.download_button(
                "Download PDF",
                pdf.content,
                file_name=f"research-{session_id[:8]}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )


@st.fragment(run_every=0.5)
def research_progress_fragment() -> None:
    if not st.session_state.watching or not st.session_state.active_session:
        return
    session_id = st.session_state.active_session

    if st.session_state.sse_consumer_session != session_id:
        start_sse_consumer(session_id)

    q: queue.Queue | None = st.session_state.get("sse_queue")
    if q is not None and not st.session_state.use_poll_fallback:
        while True:
            try:
                ev = q.get_nowait()
            except queue.Empty:
                break
            apply_research_event(ev)

    if st.session_state.use_poll_fallback:
        batch = api_get_json(
            f"/api/research/{session_id}/events/poll",
            timeout=30,
            params={"since_seq": st.session_state.last_seq},
        )
        if isinstance(batch, list):
            for ev in batch:
                apply_research_event(ev)

    detail = api_get_json(f"/api/research/{session_id}", timeout=120)
    st.session_state.progress_text = build_progress_markdown(detail)

    with st.chat_message("assistant"):
        if st.session_state.activity_line:
            st.caption(st.session_state.activity_line)
        body = (st.session_state.streaming_summary or "").strip()
        if body:
            st.markdown(body)
        elif st.session_state.progress_text:
            st.markdown(st.session_state.progress_text)
        else:
            st.markdown("_Starting research…_")

    if detail and detail.get("status") in ("complete", "failed"):
        stop_sse_consumer()
        st.session_state.watching = False
        for msg in st.session_state.messages:
            if msg.get("session_id") == session_id and msg.get("kind") == "progress":
                msg["kind"] = "report" if detail.get("status") == "complete" else "error"
        st.rerun(scope="app")


# --- Sidebar ---
api_status = fetch_api_health()
api_online = api_status.get("online", False)
health = api_status.get("data") or {}
ollama = health.get("ollama") if api_online else probe_ollama_direct()

with st.sidebar:
    st.markdown("### Local Research AI")
    if st.button("New research", use_container_width=True, type="primary"):
        new_chat()
        st.rerun()

    st.divider()
    st.markdown("**History**")
    try:
        hist = httpx.get(f"{API_BASE}/api/research/history", timeout=10).json()
        groups: dict[str, list] = {"Today": [], "Yesterday": [], "Older": []}
        for item in hist[:30]:
            groups[history_group(item.get("created_at", ""))].append(item)
        for group_name in ("Today", "Yesterday", "Older"):
            items = groups[group_name]
            if not items:
                continue
            st.markdown(f'<p class="hist-group">{group_name}</p>', unsafe_allow_html=True)
            for item in items:
                q = item.get("question", "")[:42]
                status = item.get("status", "")[:4]
                col_a, col_b = st.columns([5, 1])
                with col_a:
                    if st.button(f"{q}… [{status}]", key=f"hist-{item['id']}", use_container_width=True):
                        load_history_session(item["id"], item["question"], item["status"])
                        st.rerun()
                with col_b:
                    if st.button("×", key=f"del-{item['id']}"):
                        httpx.delete(f"{API_BASE}/api/research/{item['id']}", timeout=10)
                        st.rerun()
    except Exception:
        st.caption("Start the API to load history.")

    st.divider()
    api_dot = "status-ok" if api_online else "status-bad"
    ollama_ok = ollama.get("ollama_reachable")
    ollama_dot = "status-ok" if ollama_ok else "status-bad"
    st.markdown(
        f'<span class="status-dot {api_dot}"></span> API {"online" if api_online else "offline"}',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<span class="status-dot {ollama_dot}"></span> Ollama {OLLAMA_MODEL if ollama_ok else "offline"}',
        unsafe_allow_html=True,
    )
    if not api_online:
        st.caption(f"Start: uvicorn on {API_BASE}")
    if st.button("Refresh status", use_container_width=True):
        fetch_api_health.clear()
        st.rerun()

# --- Main ---
st.markdown('<p class="workspace-title">Research assistant</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="workspace-sub">Local deep research · Ollama + LangChain</p>',
    unsafe_allow_html=True,
)

if not api_online:
    st.warning(
        f"Backend not running at `{API_BASE}`. "
        "Run: `uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`"
    )

session_id = st.session_state.get("active_session")
show_empty = not st.session_state.messages and not session_id

if show_empty:
    st.markdown('<p class="empty-prompt">What should I research?</p>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, suggestion in enumerate(SUGGESTIONS):
        with cols[i % 2]:
            if st.button(suggestion, key=f"sug-{i}", use_container_width=True):
                st.session_state.pending_prompt = suggestion

for msg in st.session_state.messages:
    if msg.get("kind") == "progress" and st.session_state.watching:
        # Live assistant UI is rendered inside research_progress_fragment (fragment reruns).
        continue
    role = msg.get("role", "assistant")
    with st.chat_message(role):
        if msg.get("kind") == "question":
            st.markdown(msg.get("content", ""))
        elif msg.get("kind") == "error":
            st.error(msg.get("content") or "Research failed.")
        elif msg.get("kind") in ("progress", "report"):
            st.caption(msg.get("content", "Research complete."))

research_progress_fragment()

if session_id and not st.session_state.watching:
    detail = api_get_json(f"/api/research/{session_id}", timeout=120)
    if detail:
        if detail.get("status") == "failed":
            err = (detail.get("error") or "Research failed.").strip()
            st.error(err)
        elif detail.get("status") == "complete":
            if detail.get("sources_discovered", 0) == 0:
                st.warning("No web sources were retrieved in this session.")
            with st.chat_message("assistant"):
                st.markdown("Here is your research report.")
                render_report_tabs(session_id, detail)

prompt = st.session_state.pop("pending_prompt", None)
_input_mode = "disable" if st.session_state.watching else "submit"
chat_q = st.chat_input(
    "Ask a research question…",
    key="research_chat_input",
    submit_mode=_input_mode,
)
if chat_q and chat_q.strip():
    try:
        start_research(chat_q.strip())
        st.rerun()
    except Exception as exc:
        st.error(f"Could not start research: {exc}")
elif prompt:
    try:
        start_research(prompt)
        st.rerun()
    except Exception as exc:
        st.error(f"Could not start research: {exc}")
