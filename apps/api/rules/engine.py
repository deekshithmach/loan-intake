"""Rule registry. A rule is a plain function (Docs) -> list[Flag], registered with @rule.

Rules declare which documents they need; the engine skips a rule when one is missing,
so a failed extraction never crashes the checks (it is flagged separately).
"""

from collections.abc import Callable
from dataclasses import dataclass

from apps.api.schemas import W2, BankStatement, PayStub

from .flags import Flag


@dataclass
class Docs:
    paystub: PayStub | None = None
    w2: W2 | None = None
    statement: BankStatement | None = None

    @classmethod
    def from_data(cls, data: dict[str, dict]) -> "Docs":
        """data: {doc_type: model_dump(mode="json")} for docs that extracted OK."""
        models = {"paystub": PayStub, "w2": W2, "statement": BankStatement}
        return cls(**{k: models[k].model_validate(v) for k, v in data.items() if k in models})


RuleFn = Callable[[Docs], list[Flag]]


@dataclass(frozen=True)
class Rule:
    name: str
    stage: str  # "validate" (one document) | "cross_check" (several)
    needs: tuple[str, ...]
    fn: RuleFn


REGISTRY: list[Rule] = []


def rule(stage: str, *needs: str) -> Callable[[RuleFn], RuleFn]:
    def register(fn: RuleFn) -> RuleFn:
        REGISTRY.append(Rule(fn.__name__, stage, needs, fn))
        return fn

    return register


def run_rules(docs: Docs, stage: str | None = None) -> list[Flag]:
    flags: list[Flag] = []
    for r in REGISTRY:
        if (stage is None or r.stage == stage) and all(getattr(docs, n) is not None for n in r.needs):
            flags.extend(r.fn(docs))
    return flags
