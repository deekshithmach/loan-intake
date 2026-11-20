"""Scoring helpers: field accuracy, flag precision/recall, percentiles."""

from collections import defaultdict

from evals.compare import group


def pct(xs: list[bool]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def percentile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))] if s else 0.0


def flag_scores(pairs: list[tuple[set[str], set[str]]]) -> dict:
    """pairs: [(expected codes, predicted codes)] per applicant -> micro + per-code precision/recall."""
    tp, fp, fn = defaultdict(int), defaultdict(int), defaultdict(int)
    for exp, got in pairs:
        for c in exp | got:
            (tp if c in exp and c in got else fn if c in exp else fp)[c] += 1
    def pr(t, f, n):
        return {"recall": t / (t + n) if t + n else None, "precision": t / (t + f) if t + f else None,
                "tp": t, "fp": f, "fn": n}
    per = {c: pr(tp[c], fp[c], fn[c]) for c in sorted(set(tp) | set(fp) | set(fn))}
    return {"overall": pr(sum(tp.values()), sum(fp.values()), sum(fn.values())), "per_code": per}


__all__ = ["flag_scores", "group", "pct", "percentile"]
