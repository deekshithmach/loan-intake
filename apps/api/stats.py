"""Per-model statistics over processed applications. Feeds `GET /stats` and the "Model stats" tab.

Each row is an application dict from `repo.recent()`: `{"model": "...", "stats": {...} | None, ...}`.
`stats` is written by the workflow (apps/api/workflow/graph.py):
  after extraction: docs_total, docs_ok, attempts, llm_calls, input_tokens, output_tokens, latency_ms (summed
                    over the application's documents), cost_usd
  after cross-check: flags
  after the human decision: decision ("approved"/"rejected"), edits (fields the underwriter corrected),
                    flags_dismissed (false alarms), flags_accepted
Applications still processing, or run before this feature existed, have no model/stats and are skipped.

============================== LEARNING BLOCK: your turn ==============================
`_summary` below already computes runs, avg latency, avg cost and avg tokens. The metrics that need a bit
more thought are returned as None. Implement them, then remove the `xfail` marker from the matching tests in
tests/test_stats.py (they are strict: once your code is right they turn from "expected fail" to a failure
telling you to delete the marker).

  p50_latency_s / p95_latency_s   percentile of the per-application latency (seconds). Write your own
                                  nearest-rank percentile; the evals package is not in the API image.
  extraction_success_rate         sum(docs_ok) / sum(docs_total) across runs, 0..1
  reviewed                        how many runs have a "decision"
  edits_per_review                mean "edits" over reviewed runs (None if nothing reviewed yet)
  flag_dismissal_rate             sum(flags_dismissed) / (sum(flags_dismissed) + sum(flags_accepted)) over
                                  reviewed runs; None if no flags were decided. High = many false alarms.
  approval_rate                   share of reviewed runs whose decision is "approved" (None if none reviewed)
=======================================================================================
"""

from collections import defaultdict
from statistics import mean


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("model") and r.get("stats"):
            groups[r["model"]].append(r["stats"])
    return sorted((_summary(model, runs) for model, runs in groups.items()), key=lambda s: (-s["runs"], s["model"]))


def _summary(model: str, runs: list[dict]) -> dict:
    return {
        "model": model,
        "runs": len(runs),
        "avg_latency_s": round(mean(r.get("latency_ms", 0) for r in runs) / 1000, 2),
        "avg_cost_usd": round(mean(r.get("cost_usd", 0) for r in runs), 5),
        "avg_tokens": round(mean(r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in runs)),
        # TODO (yours): see the module docstring. Return real numbers instead of None.
        "p50_latency_s": None,
        "p95_latency_s": None,
        "extraction_success_rate": None,
        "reviewed": None,
        "edits_per_review": None,
        "flag_dismissal_rate": None,
        "approval_rate": None,
    }
