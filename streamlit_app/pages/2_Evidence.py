import streamlit as st

from app.copy import draft_outreach
from streamlit_app.state import candidates, get_agent_session
from streamlit_app.theme import inject_css

st.set_page_config(page_title="Evidence · TalentScout", page_icon="📋", layout="wide")
inject_css()
items = candidates()
st.markdown('<div class="eyebrow">Evidence dossiers</div>', unsafe_allow_html=True)
st.title("See why each candidate made the cut.")
if not items:
    st.info("Run a search in the Workspace first.")
    st.stop()

labels = [item.get("name") or item.get("title") or item.get("username") or "Public profile" for item in items]
selected = st.selectbox("Candidate", labels)
candidate = items[labels.index(selected)]
left, right = st.columns([1.5, 1])
with left:
    st.subheader(selected)
    st.metric("Match score", f"{candidate.get('match_score', 0)}%")
    st.write(candidate.get("bio") or candidate.get("snippet") or "No public summary available.")
    st.write("**Matched skills**", ", ".join(candidate.get("matched_skills", [])) or "No direct evidence")
    st.write("**Evidence gaps**", ", ".join(candidate.get("missing_skills", [])) or "No requested skill gaps")
    st.write("**Confidence**", candidate.get("confidence", "Medium"))
    for reason in candidate.get("confidence_reasons", []):
        st.caption(f"• {reason}")
with right:
    st.subheader("Repository evidence")
    repos = candidate.get("repositories", [])
    if repos:
        for repo in repos:
            st.markdown(
                f"**[{repo.get('name', 'Repository')}]({repo.get('url', '#')})** · "
                f"{repo.get('language') or 'language not listed'} · ★ {repo.get('stars', 0)}"
            )
            if repo.get("description"):
                st.caption(repo["description"])
    else:
        st.info("No GitHub repository evidence was available for this profile.")

st.divider()
if st.button("Generate evidence-grounded outreach draft", type="primary"):
    with st.spinner("Writing a careful draft…"):
        draft = draft_outreach(candidate, get_agent_session().requirements.get("role", "the role"))
    st.text_area("Draft — review before sending", draft, height=180)
