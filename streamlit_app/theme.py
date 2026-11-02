import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #F9F7F4 !important; color: #1B3139 !important; }
        header[data-testid="stHeader"] { background: #F9F7F4 !important; }
        [data-testid="stChatInput"], [data-testid="stChatInput"] textarea,
        .stTextInput input, .stTextArea textarea, .stNumberInput input {
            background: #FFFFFF !important; color: #1B3139 !important;
            border-color: #CBD5E1 !important;
        }
        .block-container { max-width: 1440px; padding-top: 2rem; }
        h1, h2, h3, p, label, [data-testid="stMarkdownContainer"] { color: #1B3139; }
        [data-testid="stSidebar"] { background: #FFFFFF; }
        button[kind="primary"] { background: #0D9488 !important; border-color: #0D9488 !important; }
        button[kind="secondary"] { color: #1B3139 !important; }
        .brand { color: #0D9488; font-size: 2rem; font-weight: 800; letter-spacing: -0.04em; }
        .eyebrow { color: #0D9488; text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; font-weight: 800; }
        .hero { padding: 1.4rem 1.6rem; border: 1px solid #E5E7EB; border-radius: 18px; background: white; box-shadow: 0 8px 28px rgba(27,49,57,.06); }
        .metric-card { padding: 1rem; border: 1px solid #E5E7EB; border-radius: 14px; background: white; }
        .metric-label { color: #64748B; font-size: .8rem; }
        .metric-value { color: #1B3139; font-size: 1.65rem; font-weight: 800; }
        .candidate-card { padding: 1rem 1.1rem; border: 1px solid #E5E7EB; border-radius: 14px; background: white; margin-bottom: .75rem; }
        .confidence-high { color: #047857; font-weight: 700; }
        .confidence-medium { color: #B45309; font-weight: 700; }
        .confidence-low { color: #64748B; font-weight: 700; }
        div[data-testid="stChatMessage"] { border-radius: 14px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str | int) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )
