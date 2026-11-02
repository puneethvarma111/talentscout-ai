"""LangGraph supervisor workspace for HR (legacy Streamlit UI)."""


import streamlit as st

from app.session import get_session
from app.supervisor_graph import run_supervisor

st.set_page_config(page_title="Supervisor HR Agent", page_icon="🧭", layout="wide")
st.title("TalentScout Supervisor Agent")
st.caption(
    "Hub-and-spoke multi-agent flow: Recruiting, HR Ops, and Policy workers with SQLite memory."
)

if "supervisor_thread" not in st.session_state:
    st.session_state.supervisor_thread = str(uuid.uuid4())

thread_id = st.sidebar.text_input("Conversation thread", st.session_state.supervisor_thread)
use_cases = {
    "Auto-recruit (source + rank)": (
        "We need a React frontend engineer in Bengaluru with 2–4 years experience. "
        "Source public profiles, rank them, and summarize the top five for my review."
    ),
    "Manager pipeline brief": "Give leadership a pipeline summary of everyone we have saved so far.",
    "Interview pack": "Prepare an interview question pack for our software engineer role focusing on system design and communication.",
    "HR policy + onboarding": "What is our remote work policy? Also create an onboarding checklist for a new engineer.",
}
choice = st.sidebar.selectbox("HR use case", list(use_cases.keys()))
prompt = st.text_area("Message", use_cases[choice], height=120)

if st.button("Run supervisor workflow", type="primary"):
    session = get_session(f"graph:{thread_id}")
    with st.spinner("Supervisor routing workers…"):
        result = run_supervisor(session, prompt, thread_id=thread_id)
    st.session_state.last_supervisor = result

result = st.session_state.get("last_supervisor")
if result:
    st.subheader("Assistant reply")
    st.write(result.get("reply"))
    st.subheader("Activity trace")
    for step in result.get("steps") or []:
        st.markdown(f"- {step}")
    if result.get("candidates"):
        st.subheader("Shortlist")
        st.dataframe(
            [
                {
                    "name": c.get("name") or c.get("username"),
                    "score": c.get("match_score"),
                    "skills": ", ".join(c.get("matched_skills") or []),
                }
                for c in result["candidates"][:10]
            ],
            use_container_width=True,
        )
    if result.get("management_brief"):
        st.subheader("Management brief")
        st.json(result["management_brief"])
    if result.get("interview_pack"):
        st.subheader("Interview pack")
        st.json(result["interview_pack"])
