"""Provider-agnostic LLM interface. Pipeline code depends only on this file."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import asdict, dataclass

# USD per 1M tokens (input, output). Unknown models log cost 0.0.
PRICES: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.8-flash": (0.75, 3.75),  # intro price thru 2026-12-31; $1.50/$7.50 from 2027

    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
}


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(*(a + b for a, b in zip(asdict(self).values(), asdict(other).values())))

    @classmethod
    def priced(cls, model: str, input_tokens: int, output_tokens: int, latency_ms: float) -> "Usage":
        pin, pout = PRICES.get(model, (0.0, 0.0))
        cost = (input_tokens * pin + output_tokens * pout) / 1_000_000
        return cls(1, input_tokens, output_tokens, round(latency_ms, 1), cost)


@dataclass
class LLMResponse:
    text: str
    usage: Usage


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate(self, prompt: str, images: Sequence[bytes] = (), json_mode: bool = True) -> LLMResponse:
        """Send a prompt (+ optional PNG page images); return raw text + usage."""
