import pandas as pd
import plotly.express as px
import streamlit as st

from streamlit_app.state import candidates, get_agent_session
from streamlit_app.theme import inject_css

st.set_page_config(page_title="Compare · TalentScout", page_icon="📊", layout="wide")
inject_css()
items = candidates()[:3]
st.markdown('<div class="eyebrow">Shortlist intelligence</div>', unsafe_allow_html=True)
st.title("Compare the top three at a glance.")
if not items:
    st.info("Run a search in the Workspace first.")
    st.stop()

skills = get_agent_session().requirements.get("skills", [])
rows = []
for item in items:
    name = item.get("name") or item.get("title") or item.get("username") or "Candidate"
    matched = {skill.lower() for skill in item.get("matched_skills", [])}
    for skill in skills:
        rows.append({"Candidate": name, "Skill": skill, "Evidence": 1 if skill.lower() in matched else 0})
    if not skills:
        rows.append({"Candidate": name, "Skill": "Overall match", "Evidence": item.get("match_score", 0) / 100})

chart = px.bar(
    pd.DataFrame(rows),
    x="Skill",
    y="Evidence",
    color="Candidate",
    barmode="group",
    range_y=[0, 1],
    labels={"Evidence": "Observed evidence"},
    color_discrete_sequence=["#0D9488", "#F59E0B", "#64748B"],
)
chart.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", height=420)
st.plotly_chart(chart, use_container_width=True)
st.dataframe(
    pd.DataFrame(
        [
            {
                "Candidate": item.get("name") or item.get("title") or item.get("username"),
                "Match": f"{item.get('match_score', 0)}%",
                "Confidence": item.get("confidence", "Medium"),
                "Location": item.get("location") or "Not listed",
            }
            for item in items
        ]
    ),
    hide_index=True,
    use_container_width=True,
)
