"""Prompt templates adapted from langchain-ai/local-deep-researcher (MIT)."""

from __future__ import annotations

from datetime import datetime


def current_date_str() -> str:
    return datetime.now().strftime("%B %d, %Y")


QUERY_WRITER_SYSTEM = """You generate targeted web search queries for research.
Current date context should inform recency. Output structured JSON only."""

SUMMARIZER_SYSTEM = """Generate a high-quality summary of the provided search context.

When creating a NEW summary:
- Highlight information most relevant to the user topic
- Ensure coherent flow

When EXTENDING an existing summary:
- Integrate new relevant facts into existing paragraphs or add new paragraphs
- Skip information not relevant to the topic
- Do not repeat the prior summary verbatim

Start directly with the updated summary. No preamble or titles."""

REFLECTION_SYSTEM = """You are an expert research assistant analyzing a running summary.
Identify knowledge gaps, propose one follow-up web search question, and decide if evidence is sufficient for a final report.
The follow-up question must be self-contained for web search."""
