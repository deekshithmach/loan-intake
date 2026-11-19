"""Field-level comparison of extracted output vs truth.json fields."""

from typing import Any


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(obj, dict):
        return {k: v for key, val in obj.items() for k, v in flatten(val, f"{prefix}{key}.").items()}
    if isinstance(obj, list):
        return {k: v for i, val in enumerate(obj) for k, v in flatten(val, f"{prefix}{i}.").items()}
    return {prefix.rstrip("."): obj}


def norm(v: Any) -> Any:
    return " ".join(v.upper().split()) if isinstance(v, str) else v


def score(pred: dict | None, truth: dict) -> dict[str, bool]:
    """{truth field path: matched}. Missing/failed extraction = all fields wrong."""
    p = flatten(pred or {})
    return {k: k in p and norm(p[k]) == norm(v) for k, v in flatten(truth).items()}


def group(path: str) -> str:
    return "transactions" if path.startswith("transactions.") else "header"
