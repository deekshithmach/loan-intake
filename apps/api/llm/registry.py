"""Models the UI can offer. A model is selectable only when the API key for its provider is configured."""

from dataclasses import dataclass

from apps.api.config import Settings


@dataclass(frozen=True)
class ModelInfo:
    id: str  # what the provider's API calls it
    label: str
    provider: str  # gemini | anthropic | groq | openrouter
    free: bool  # runs on a provider's free tier (list-price cost is still tracked where we know it)


MODELS: list[ModelInfo] = [
    ModelInfo("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", "gemini", True),
    ModelInfo("gemini-3.5-flash", "Gemini 3.5 Flash", "gemini", True),
    ModelInfo("qwen/qwen3.8-27b", "Qwen 3.8 27B (Groq)", "groq", True),
    ModelInfo("nvidia/nemotron-3.5-super-vl:free", "Nemotron 3.5 Super VL (OpenRouter)", "openrouter", True),
    ModelInfo("google/gemma-4-31b-it:free", "Gemma 4 31B (OpenRouter)", "openrouter", True),
    ModelInfo("claude-haiku-5-5", "Claude Haiku 5.5 (paid)", "anthropic", False),
]
BY_ID = {m.id: m for m in MODELS}
BASE_URLS = {"groq": "https://api.groq.com/openai/v1", "openrouter": "https://openrouter.ai/api/v1"}


def api_key(provider: str, s: Settings):
    return {"gemini": s.gemini_api_key, "anthropic": s.anthropic_api_key, "groq": s.groq_api_key,
            "openrouter": s.openrouter_api_key}.get(provider)


def listing(s: Settings | None = None) -> list[dict]:
    """Every known model with `available` (its key is set). The default comes first among available ones."""
    s = s or Settings()
    rows = [{"id": m.id, "label": m.label, "provider": m.provider, "free": m.free,
             "available": api_key(m.provider, s) is not None} for m in MODELS]
    default = s.llm_model or next((r["id"] for r in rows if r["available"]), None)
    return [{**r, "default": r["id"] == default} for r in rows]
