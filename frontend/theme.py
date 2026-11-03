"""Dark ChatGPT-inspired layout CSS for Streamlit."""

from __future__ import annotations

import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
<style>
  /* Center main chat column */
  section.main > div.block-container {
    max-width: 48rem;
    padding-top: 1.5rem;
    padding-bottom: 6rem;
  }
  .workspace-title {
    font-size: 1.35rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin-bottom: 0.15rem;
  }
  .workspace-sub {
    color: #9b9b9b;
    font-size: 0.9rem;
    margin-bottom: 1.25rem;
  }
  .empty-prompt {
    text-align: center;
    color: #b4b4b4;
    padding: 2rem 0 1rem;
    font-size: 1.1rem;
  }
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
  }
  .status-ok { background: #10a37f; }
  .status-bad { background: #ef4444; }
  div[data-testid="stSidebar"] {
    background-color: #171717;
  }
  .hist-group {
    font-size: 0.75rem;
    font-weight: 600;
    color: #888;
    text-transform: uppercase;
    margin: 0.75rem 0 0.35rem;
  }
</style>
""",
        unsafe_allow_html=True,
    )
