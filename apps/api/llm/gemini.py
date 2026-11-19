import logging
import time
from collections.abc import Sequence

from google import genai
from google.genai import errors, types

from .base import LLMProvider, LLMResponse, Usage

log = logging.getLogger(__name__)
RETRYABLE = {429, 500, 503}


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, max_retries: int = 4):
        self.model = model
        self.max_retries = max_retries
        self._client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, images: Sequence[bytes] = (), json_mode: bool = True) -> LLMResponse:
        contents = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images]
        contents.append(prompt)
        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                resp = self._client.models.generate_content(model=self.model, contents=contents, config=config)
                break
            except errors.APIError as e:  # transport-level retry (rate limit / overload), not output retry
                if e.code not in RETRYABLE or attempt == self.max_retries:
                    raise
                wait = 15 * (attempt + 1)
                log.warning("gemini %s, retrying in %ss", e.code, wait)
                time.sleep(wait)
        latency = (time.perf_counter() - t0) * 1000
        um = resp.usage_metadata
        out_tokens = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
        usage = Usage.priced(self.model, um.prompt_token_count or 0, out_tokens, latency)
        return LLMResponse(text=resp.text or "", usage=usage)
