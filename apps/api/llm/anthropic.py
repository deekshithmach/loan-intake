import base64
import logging
import time
from collections.abc import Sequence

import anthropic

from .base import LLMProvider, LLMResponse, Usage

log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int = 8000):
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=4)  # SDK retries 429/5xx itself

    def generate(self, prompt: str, images: Sequence[bytes] = (), json_mode: bool = True) -> LLMResponse:
        content: list[dict] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.standard_b64encode(img).decode()}}
            for img in images
        ]
        content.append({"type": "text", "text": prompt})
        t0 = time.perf_counter()
        # No temperature (rejected on 5.x models); low effort = little thinking, cheap and fast for extraction
        extra = {"system": "Reply with a single JSON object only. No prose, no markdown fences."} if json_mode else {}
        resp = self._client.messages.create(
            model=self.model, max_tokens=self.max_tokens, output_config={"effort": "low"},
            messages=[{"role": "user", "content": content}], **extra,
        )
        latency = (time.perf_counter() - t0) * 1000
        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = Usage.priced(self.model, resp.usage.input_tokens, resp.usage.output_tokens, latency)
        return LLMResponse(text=text, usage=usage)
