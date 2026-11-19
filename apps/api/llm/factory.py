from apps.api.config import Settings

from .base import LLMProvider

DEFAULT_MODELS = {"gemini": "gemini-3.5-flash-lite"}  # fast, no thinking; 3.8-flash thinks ~minutes per doc


def get_provider(settings: Settings | None = None, model: str | None = None) -> LLMProvider:
    s = settings or Settings()
    model = model or s.llm_model or DEFAULT_MODELS.get(s.llm_provider, "")
    if s.llm_provider == "gemini":
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        from .gemini import GeminiProvider  # lazy: only import the SDK you use

        return GeminiProvider(s.gemini_api_key.get_secret_value(), model)
    raise ValueError(f"provider not implemented yet: {s.llm_provider}")
