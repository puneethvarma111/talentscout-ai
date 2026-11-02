import tempfile
from pathlib import Path

import streamlit as st
from faster_whisper import WhisperModel

from streamlit_app.state import candidates, execute_agent, get_agent_session
from streamlit_app.theme import inject_css

st.set_page_config(page_title="Workspace · TalentScout", page_icon="🔍", layout="wide")
inject_css()

session = get_agent_session()
st.markdown('<div class="eyebrow">Agent workspace</div>', unsafe_allow_html=True)
st.title("Find the people behind the keywords.")
st.caption("Ask naturally. The agent will decide when to search, rank, and explain.")

with st.expander("Start from a job description or voice brief", expanded=not bool(st.session_state.get("chat_history"))):
    jd = st.text_area(
        "Paste a JD or hiring brief",
        value=st.session_state.get("jd_text", ""),
        height=130,
        placeholder="We are hiring a senior backend engineer to build...",
    )
    audio = st.audio_input("Or record a voice brief")
    if audio:
        with st.spinner("Transcribing locally…"):
            model = WhisperModel("base", device="cpu", compute_type="int8")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                handle.write(audio.getvalue())
                audio_path = handle.name
            segments, _ = model.transcribe(audio_path, vad_filter=True)
            Path(audio_path).unlink(missing_ok=True)
            st.session_state.jd_text = " ".join(segment.text.strip() for segment in segments).strip()
            jd = st.session_state.jd_text
        st.success("Voice brief ready. Review it, then run the agent.")
    if st.button("Analyze brief and build shortlist", type="primary"):
        if jd.strip():
            st.session_state.jd_text = jd.strip()
            st.session_state.pending_prompt = jd.strip()
            st.rerun()
        else:
            st.warning("Paste a brief or record one first.")

with st.sidebar:
    st.subheader("Job brief")
    role = st.text_input("Role", value=session.requirements.get("role", ""))
    skills = st.text_input("Skills", value=", ".join(session.requirements.get("skills", [])))
    location = st.text_input("Location", value=session.requirements.get("location", ""))
    min_years = st.number_input("Minimum years", min_value=0.0, value=float(session.requirements.get("min_years", 0)))
    max_years = st.number_input("Maximum years", min_value=0.0, value=float(session.requirements.get("max_years", 99)))
    if st.button("Apply brief", use_container_width=True):
        session.requirements.update(
            {
                "role": role,
                "skills": [item.strip() for item in skills.split(",") if item.strip()],
                "location": location,
                "min_years": min_years,
                "max_years": max_years,
            }
        )
        st.success("Brief updated.")

pending = st.session_state.pop("pending_prompt", None)
if pending:
    st.session_state.chat_history = st.session_state.get("chat_history", [])
    st.session_state.chat_history.append(("user", pending))
    with st.status("TalentScout is working…", expanded=True) as status:
        result = execute_agent(pending, on_step=lambda step: st.write(f"✓ {step}"))
        status.update(label="Shortlist ready", state="complete")
    st.session_state.chat_history.append(("assistant", result["reply"]))
    st.rerun()

for role_name, message in st.session_state.get("chat_history", []):
    with st.chat_message(role_name):
        st.markdown(message)

prompt = st.chat_input("Describe a role, refine the search, or ask about a candidate…")
if prompt:
    st.session_state.chat_history = st.session_state.get("chat_history", [])
    st.session_state.chat_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.status("TalentScout is working…", expanded=True) as status:
            result = execute_agent(prompt, on_step=lambda step: st.write(f"✓ {step}"))
            status.update(label="Analysis complete", state="complete")
        st.markdown(result["reply"])
    st.session_state.chat_history.append(("assistant", result["reply"]))
    st.rerun()

st.divider()
st.subheader("Live shortlist")
items = candidates()
if not items:
    st.info("Your shortlist will appear here after the first request.")
for item in items:
    confidence = item.get("confidence", "Medium")
    css = confidence.lower()
    with st.container():
        st.markdown(
            f'<div class="candidate-card"><strong>{item.get("name") or item.get("title") or "Public profile"}</strong>'
            f'<span style="float:right">{item.get("match_score", 0)}%</span><br>'
            f'<span class="confidence-{css}">{confidence} confidence</span> · '
            f'{", ".join(item.get("matched_skills", [])) or "No direct skill evidence"}<br>'
            f'<small>{item.get("bio") or item.get("snippet") or "No public summary available"}</small></div>',
            unsafe_allow_html=True,
        )
