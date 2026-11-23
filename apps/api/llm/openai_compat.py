"""Provider for any OpenAI-compatible /chat/completions API with image input (Groq, OpenRouter, ...)."""

import base64
import logging
import time
from collections.abc import Sequence

import httpx

from .base import LLMProvider, LLMResponse, Usage

log = logging.getLogger(__name__)
RETRYABLE = {429, 500, 502, 503}


class OpenAICompatProvider(LLMProvider):
    def __init__(self, name: str, base_url: str, api_key: str, model: str, max_retries: int = 3,
                 client: httpx.Client | None = None):
        self.name, self.model, self.max_retries = name, model, max_retries
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.Client(timeout=120)

    def _body(self, prompt: str, images: Sequence[bytes], json_mode: bool) -> dict:
        content: list[dict] = [{"type": "image_url",
                                "image_url": {"url": "data:image/png;base64," + base64.b64encode(i).decode()}}
                               for i in images]
        content.append({"type": "text", "text": prompt})
        body = {"model": self.model, "temperature": 0, "max_tokens": 8000,
                "messages": [{"role": "user", "content": content}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def generate(self, prompt: str, images: Sequence[bytes] = (), json_mode: bool = True) -> LLMResponse:
        body = self._body(prompt, images, json_mode)
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            r = self._client.post(self._url, json=body, headers=self._headers)
            if r.status_code == 400 and "response_format" in body and "response_format" in r.text.lower():
                body.pop("response_format")  # some models reject JSON mode; the prompt still asks for JSON
                continue
            if r.status_code in RETRYABLE and attempt < self.max_retries:
                wait = 15 * (attempt + 1)
                log.warning("%s %s, retrying in %ss", self.name, r.status_code, wait)
                time.sleep(wait)
                continue
            break
        latency = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            # Don't echo the response body into exceptions that end up in the audit log: keep it short.
            raise RuntimeError(f"{self.name} HTTP {r.status_code}: {r.text[:200]}")
        j = r.json()
        u = j.get("usage") or {}
        text = (j["choices"][0]["message"].get("content") or "")
        return LLMResponse(text=text, usage=Usage.priced(self.model, u.get("prompt_tokens", 0),
                                                         u.get("completion_tokens", 0), latency))
