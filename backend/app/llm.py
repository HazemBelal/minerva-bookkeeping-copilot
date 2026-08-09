from __future__ import annotations

from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from .config import settings

# One provider-agnostic async client. Whatever LLM_BASE_URL names — local
# Ollama, OpenAI, or Gemini's OpenAI-compatible endpoint — the rest of the
# app is identical. The OpenAI SDK requires a non-empty api_key even when the
# server ignores it (Ollama), hence the "ollama" literal default.
client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
MODEL = settings.llm_model
USE_VISION = settings.llm_use_vision

T = TypeVar("T", bound=BaseModel)


async def structured_completion(system: str, user: str, schema: type[T]) -> T | None:
    """Return a validated `schema` instance from the model.

    Tries the OpenAI structured-output path (`.parse()` with the pydantic
    model). If the server does not support it (older Ollama returns a 400 or
    ignores the schema), falls back to JSON mode with the schema injected into
    the prompt, then validates. Returns None if nothing parseable comes back —
    callers must handle None, never assume success.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        resp = await client.beta.chat.completions.parse(
            model=MODEL, temperature=0, messages=messages, response_format=schema
        )
        parsed = resp.choices[0].message.parsed
        if parsed is not None:
            return parsed
    except Exception:
        pass  # fall through to JSON-mode fallback

    schema_json = schema.model_json_schema()
    fallback_messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"{user}\n\nRespond with ONLY a JSON object matching this JSON "
                f"schema (no markdown, no prose):\n{schema_json}"
            ),
        },
    ]
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=fallback_messages,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or ""
        return schema.model_validate_json(content)
    except Exception:
        return None
