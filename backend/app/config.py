from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    runs_dir: Path = Path(os.getenv("RUNS_DIR", "runs"))
    max_steps_per_merchant: int = int(os.getenv("MAX_STEPS_PER_MERCHANT", "6"))
    max_merchants: int = int(os.getenv("MAX_MERCHANTS", "8"))
    concurrency: int = int(os.getenv("CONCURRENCY", "2"))
    runs_per_ip_per_hour: int = int(os.getenv("RUNS_PER_IP_PER_HOUR", "3"))


settings = Settings()
settings.runs_dir.mkdir(parents=True, exist_ok=True)
