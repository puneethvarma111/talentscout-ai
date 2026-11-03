# Third-party adaptations

## langchain-ai/local-deep-researcher

- **Repository:** https://github.com/langchain-ai/local-deep-researcher
- **License:** MIT
- **What we adapted:** IterDRAG-style iterative loop (web search → summarize → reflect → follow-up query), prompt structure, and context formatting ideas.
- **What we did not use:** LangGraph runtime, LangGraph Studio, LMStudio/Tavily-specific paths as required dependencies.

### Local files influenced by upstream

| File | Notes |
|------|--------|
| [`app/agent/ldr_prompts.py`](../app/agent/ldr_prompts.py) | Adapted query writer, summarizer, and reflection prompt templates |
| [`app/agent/ldr_reflection.py`](../app/agent/ldr_reflection.py) | Reflection step producing follow-up queries |
| [`app/research/running_summary.py`](../app/research/running_summary.py) | Running summary accumulation across iterations |

Orchestration remains in plain Python in [`app/research/research_service.py`](../app/research/research_service.py).
