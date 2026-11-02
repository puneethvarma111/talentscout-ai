import pandas as pd
import streamlit as st

from streamlit_app.state import candidates, get_agent_session
from streamlit_app.theme import inject_css

st.set_page_config(page_title="Export · TalentScout", page_icon="📤", layout="wide")
inject_css()
items = candidates()
st.markdown('<div class="eyebrow">Client pack</div>', unsafe_allow_html=True)
st.title("Take a defensible shortlist to the hiring team.")
if not items:
    st.info("Run a search in the Workspace first.")
    st.stop()

selected = st.multiselect("Include candidates", range(len(items)), default=list(range(min(5, len(items)))),
                          format_func=lambda i: items[i].get("name") or items[i].get("title") or "Public profile")
chosen = [items[i] for i in selected]
table = pd.DataFrame(
    [
        {
            "Name": item.get("name") or item.get("title") or item.get("username"),
            "Match": item.get("match_score", 0),
            "Confidence": item.get("confidence", "Medium"),
            "Matched skills": ", ".join(item.get("matched_skills", [])),
            "Profile": item.get("profile_url") or item.get("url", ""),
            "Evidence": " | ".join(item.get("evidence", [])),
        }
        for item in chosen
    ]
)
st.dataframe(table, hide_index=True, use_container_width=True)
csv = table.to_csv(index=False).encode("utf-8")
st.download_button("Download shortlist CSV", csv, "talentscout-shortlist.csv", "text/csv", type="primary")

role = get_agent_session().requirements.get("role", "open role")
markdown = f"# TalentScout shortlist\n\n**Role:** {role}\n\n"
for index, item in enumerate(chosen, 1):
    markdown += (
        f"## {index}. {item.get('name') or item.get('title') or 'Public profile'} — "
        f"{item.get('match_score', 0)}% match\n"
        f"- Confidence: {item.get('confidence', 'Medium')}\n"
        f"- Evidence: {'; '.join(item.get('evidence', []))}\n"
        f"- Profile: {item.get('profile_url') or item.get('url', 'Not listed')}\n\n"
    )
st.download_button("Download client-ready Markdown", markdown, "talentscout-pack.md", "text/markdown")
