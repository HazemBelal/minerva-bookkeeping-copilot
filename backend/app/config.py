from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:14b")
    llm_api_key: str = os.getenv("LLM_API_KEY", "ollama")
    llm_use_vision: bool = os.getenv("LLM_USE_VISION", "true").lower() == "true"
    # Ollama defaults new sessions to a 4096-token context window regardless
    # of what the model itself supports. browser-use's DOM-heavy prompts
    # blow past that (observed 7.7k-13.9k tokens for a single research step),
    # so the local-Ollama path in researcher.py requests a larger window
    # explicitly. Irrelevant for the OpenAI/Gemini fallback path.
    llm_ollama_num_ctx: int = int(os.getenv("LLM_OLLAMA_NUM_CTX", "16384"))
    runs_dir: Path = Path(os.getenv("RUNS_DIR", "runs"))
    max_steps_per_merchant: int = int(os.getenv("MAX_STEPS_PER_MERCHANT", "6"))
    max_merchants: int = int(os.getenv("MAX_MERCHANTS", "8"))
    concurrency: int = int(os.getenv("CONCURRENCY", "2"))
    runs_per_ip_per_hour: int = int(os.getenv("RUNS_PER_IP_PER_HOUR", "3"))


settings = Settings()
settings.runs_dir.mkdir(parents=True, exist_ok=True)
