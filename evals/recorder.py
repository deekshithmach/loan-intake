"""Record/replay wrapper around any LLMProvider, with a hard spend cap.

- Every LLM response is stored under a key (applicant/file) in evals/recordings/<model>/<variant>.json.
- Re-running replays stored responses for free; only missing calls hit the API. A crash or OOM loses nothing.
- `offline=True` (CI) never calls the API: a missing recording is an error.
- Recordings are tied to a hash of the prompt templates; change a prompt and they are re-recorded.
"""

import hashlib
import json
from collections.abc import Sequence

from apps.api.config import ROOT
from apps.api.llm import LLMProvider, LLMResponse, Usage

RECORDINGS = ROOT / "evals" / "recordings"
PROMPTS_SHA = hashlib.sha256((ROOT / "apps/api/extraction/prompts.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:12]


class BudgetExceeded(RuntimeError):
    pass


class OfflineMiss(RuntimeError):
    pass


class RecordingProvider(LLMProvider):
    def __init__(self, inner: LLMProvider | None, model: str, variant: str, *, offline: bool = False,
                 budget_usd: float = 1.0, rerecord: bool = False):
        self.inner, self.model, self.name = inner, model, getattr(inner, "name", "replay")
        self.offline, self.budget, self.spent, self.live_calls, self.replayed = offline, budget_usd, 0.0, 0, 0
        self.path = RECORDINGS / model / f"{variant}.json"
        self.store: dict[str, list[dict]] = {}
        if self.path.exists() and not rerecord:
            data = json.loads(self.path.read_text())
            if data.get("prompts_sha") == PROMPTS_SHA:
                self.store = data["calls"]
            elif offline:
                raise OfflineMiss(f"{self.path.name}: prompts changed since recording; run `make eval` to re-record")
        elif offline:
            raise OfflineMiss(f"no recording at {self.path}")
        self._key, self._n = "", 0

    def use(self, key: str) -> None:
        self._key, self._n = key, 0

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"prompts_sha": PROMPTS_SHA, "model": self.model, "calls": self.store}, indent=1))

    def generate(self, prompt: str, images: Sequence[bytes] = (), json_mode: bool = True) -> LLMResponse:
        calls = self.store.setdefault(self._key, [])
        if self._n < len(calls):
            rec = calls[self._n]
            self._n += 1
            self.replayed += 1
            return LLMResponse(rec["text"], Usage(**rec["usage"]))
        if self.offline or self.inner is None:
            raise OfflineMiss(f"no recording for {self._key} call #{self._n}")
        if self.spent >= self.budget:
            raise BudgetExceeded(f"spend cap ${self.budget:.2f} reached (spent ${self.spent:.4f})")
        resp = self.inner.generate(prompt, images, json_mode)
        self.spent += resp.usage.cost_usd
        self.live_calls += 1
        calls.append({"text": resp.text, "usage": resp.usage.__dict__})
        self._n += 1
        return resp
