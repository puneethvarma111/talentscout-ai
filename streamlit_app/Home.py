import os
import sys
from pathlib import Path

import streamlit as st

# Streamlit executes the entrypoint as a script; make the repository package
# importable without requiring users to set PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from streamlit_app.state import candidates, get_agent_session
from streamlit_app.theme import inject_css, metric_card

st.set_page_config(page_title="TalentScout", page_icon="🔍", layout="wide")
inject_css()

session = get_agent_session()
items = candidates()
average = round(sum(item.get("match_score", 0) for item in items) / len(items)) if items else 0

st.markdown('<div class="brand">TalentScout</div>', unsafe_allow_html=True)
st.caption("Evidence-led talent sourcing for teams that hire with confidence.")
st.markdown(
    '<div class="hero"><div class="eyebrow">Recruiting command center</div>'
    "<h1>Turn a hiring brief into a defensible shortlist.</h1>"
    "<p>Describe the role. TalentScout searches public sources, verifies visible evidence, "
    "and gives your team a shortlist they can explain.</p></div>",
    unsafe_allow_html=True,
)

st.write("")
cols = st.columns(4)
with cols[0]:
    metric_card("Active role", "1" if session.requirements.get("role") else "—")
with cols[1]:
    metric_card("Candidates sourced", len(items))
with cols[2]:
    metric_card("Shortlisted", len(items))
with cols[3]:
    metric_card("Average match", f"{average}%" if items else "—")

st.write("")
left, right = st.columns([1.4, 1])
with left:
    st.subheader("Start with a recruiter request")
    prompt = st.text_area(
        "What are you hiring for?",
        placeholder="Senior backend engineer in Bengaluru, Python, FastAPI, PostgreSQL, 4+ years...",
        height=120,
    )
    if st.button("Build my shortlist", type="primary", use_container_width=True):
        if prompt.strip():
            st.session_state.pending_prompt = prompt.strip()
            st.switch_page("pages/1_Workspace.py")
        else:
            st.warning("Describe a role first.")
with right:
    st.subheader("Your workspace")
    st.page_link("pages/1_Workspace.py", label="Agent workspace", icon="🔍")
    st.page_link("pages/2_Evidence.py", label="Evidence dossiers", icon="📋")
    st.page_link("pages/3_Compare.py", label="Compare shortlist", icon="📊")
    st.page_link("pages/4_Pipeline.py", label="Pipeline", icon="📌")
    st.page_link("pages/5_Export.py", label="Export client pack", icon="📤")
    st.caption(f"Local model: {os.getenv('OLLAMA_MODEL', 'qwen3.5:4b')}")
