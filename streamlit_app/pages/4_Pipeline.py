import streamlit as st

from app.store import list_candidates, save_candidates, set_stage
from streamlit_app.state import candidates
from streamlit_app.theme import inject_css

st.set_page_config(page_title="Pipeline · TalentScout", page_icon="📌", layout="wide")
inject_css()
items = candidates()
if items:
    save_candidates(items)
stored = list_candidates()
st.markdown('<div class="eyebrow">Hiring workflow</div>', unsafe_allow_html=True)
st.title("Keep the team aligned after sourcing.")
st.caption("Move profiles through a lightweight review pipeline. Nothing is contacted automatically.")
if not stored:
    st.info("Run a search in the Workspace first.")
    st.stop()

columns = st.columns(3)
for column, stage in zip(columns, ("Sourced", "Shortlisted", "Outreach ready")):
    with column:
        st.subheader(stage)
        stage_items = [item for item in stored if item.get("pipeline_stage") == stage]
        for item in stage_items:
            name = item.get("name") or item.get("title") or item.get("username") or "Public profile"
            st.markdown(
                f'<div class="candidate-card"><strong>{name}</strong><br>'
                f'{item.get("match_score", 0)}% · {item.get("confidence", "Medium")} confidence</div>',
                unsafe_allow_html=True,
            )
            key = item["candidate_key"]
            options = [value for value in ("Sourced", "Shortlisted", "Outreach ready") if value != stage]
            next_stage = st.selectbox("Move to", options, key=f"stage-{key}")
            if st.button("Update", key=f"update-{key}"):
                set_stage(key, next_stage)
                st.rerun()
