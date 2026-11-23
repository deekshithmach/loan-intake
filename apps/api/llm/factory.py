from apps.api.config import Settings

from .base import LLMProvider

DEFAULT_MODELS = {"gemini": "gemini-3.5-flash-lite", "anthropic": "claude-haiku-5-5"}


def provider_for(model: str, default: str) -> str:
    from .registry import BY_ID

    if model in BY_ID:
        return BY_ID[model].provider
    return "anthropic" if model.startswith("claude-") else "gemini" if model.startswith("gemini-") else default


def get_provider(settings: Settings | None = None, model: str | None = None) -> LLMProvider:
    s = settings or Settings()
    name = provider_for(model, s.llm_provider) if model else s.llm_provider
    model = model or s.llm_model or DEFAULT_MODELS.get(name, "")
    if name == "gemini":
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        from .gemini import GeminiProvider  # lazy: only import the SDK you use

        return GeminiProvider(s.gemini_api_key.get_secret_value(), model)
    if name == "anthropic":
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        from .anthropic import AnthropicProvider

        return AnthropicProvider(s.anthropic_api_key.get_secret_value(), model)
    if name in ("groq", "openrouter"):
        from .openai_compat import OpenAICompatProvider
        from .registry import BASE_URLS, api_key

        key = api_key(name, s)
        if not key:
            raise RuntimeError(f"{name.upper()}_API_KEY is not set")
        return OpenAICompatProvider(name, BASE_URLS[name], key.get_secret_value(), model)
    raise ValueError(f"provider not implemented yet: {name}")
