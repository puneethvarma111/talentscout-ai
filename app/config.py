from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

ResearchMode = Literal["fast", "balanced", "thorough"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_model: str = "llama3.2:3b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_num_ctx: int = 8192
    ollama_num_predict: int = 1024

    research_mode: ResearchMode = "balanced"

    max_research_iterations: int = 3
    max_search_results: int = 8
    max_pages_per_iteration: int = 5
    max_tool_calls: int = 40
    max_tool_rounds: int = 8
    http_timeout_sec: float = 20.0
    max_page_bytes: int = 1_500_000
    max_question_length: int = 4000

    structured_output_retries: int = 2
    skip_llm_page_extract: bool | None = None

    @field_validator("skip_llm_page_extract", mode="before")
    @classmethod
    def _empty_skip_extract_as_none(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return value

    use_ldr_loop: bool = True
    fetch_full_page: bool = False

    enable_summary_streaming: bool = True
    sse_poll_interval_sec: float = 0.4
    summary_context_max_chars: int = 14_000

    api_base_url: str = "http://127.0.0.1:8000"
    database_path: str = "data/research.sqlite3"

    @property
    def db_path(self) -> Path:
        p = Path(self.database_path)
        return p if p.is_absolute() else ROOT / p

    @property
    def reports_dir(self) -> Path:
        d = ROOT / "reports"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def effective_skip_llm_page_extract(self) -> bool:
        if self.skip_llm_page_extract is not None:
            return self.skip_llm_page_extract
        return self.research_mode == "fast"

    @property
    def effective_max_research_iterations(self) -> int:
        if self.research_mode == "fast":
            return min(self.max_research_iterations, 1)
        if self.research_mode == "thorough":
            return max(self.max_research_iterations, 5)
        return self.max_research_iterations

    @property
    def effective_max_pages_per_iteration(self) -> int:
        if self.research_mode == "fast":
            return min(self.max_pages_per_iteration, 2)
        return self.max_pages_per_iteration

    @property
    def effective_max_search_results(self) -> int:
        if self.research_mode == "fast":
            return min(self.max_search_results, 5)
        return self.max_search_results

    @property
    def effective_structured_output_retries(self) -> int:
        if self.research_mode == "fast":
            return min(self.structured_output_retries, 1)
        return self.structured_output_retries

    @property
    def effective_summary_context_max_chars(self) -> int:
        if self.research_mode == "fast":
            return min(self.summary_context_max_chars, 8000)
        return self.summary_context_max_chars

    @property
    def effective_ollama_num_ctx(self) -> int:
        if self.research_mode == "fast":
            return min(self.ollama_num_ctx, 4096)
        return self.ollama_num_ctx

    @property
    def effective_ollama_num_predict(self) -> int:
        if self.research_mode == "fast":
            return min(self.ollama_num_predict, 512)
        return self.ollama_num_predict

    @property
    def is_fast_mode(self) -> bool:
        return self.research_mode == "fast"


@lru_cache
def get_settings() -> Settings:
    return Settings()
