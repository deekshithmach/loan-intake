"""summarize(): the first test passes today; the rest are the learning block (see apps/api/stats.py)."""

import pytest

from apps.api.stats import summarize

TODO = pytest.mark.xfail(strict=True, reason="learning block: implement in apps/api/stats.py, then delete this marker")


def run(model, latency_ms=1000, cost=0.01, docs=(3, 3), tokens=(100, 50), **after):
    stats = {"latency_ms": latency_ms, "cost_usd": cost, "docs_total": docs[1], "docs_ok": docs[0],
             "input_tokens": tokens[0], "output_tokens": tokens[1], **after}
    return {"model": model, "stats": stats}


ROWS = [
    run("a", 1000, 0.02, edits=2, flags_dismissed=1, flags_accepted=3, decision="approved"),
    run("a", 3000, 0.04, docs=(2, 3), edits=0, flags_dismissed=1, flags_accepted=0, decision="rejected"),
    run("a", 2000, 0.00),  # not reviewed yet
    run("b", 500, 0.0),
    {"model": "a", "stats": None},  # still processing: skipped
    {"model": None, "stats": {"latency_ms": 1}},  # no model recorded: skipped
]


def by_model():
    return {s["model"]: s for s in summarize(ROWS)}


def test_groups_and_averages():
    s = by_model()
    assert list(s) == ["a", "b"]  # most runs first
    assert s["a"]["runs"] == 3 and s["b"]["runs"] == 1
    assert s["a"]["avg_latency_s"] == 2.0
    assert s["a"]["avg_cost_usd"] == 0.02
    assert s["a"]["avg_tokens"] == 150


@TODO
def test_latency_percentiles():
    a = by_model()["a"]
    assert a["p50_latency_s"] == 2.0 and a["p95_latency_s"] == 3.0  # nearest-rank over [1.0, 2.0, 3.0]


@TODO
def test_extraction_success_rate():
    assert by_model()["a"]["extraction_success_rate"] == pytest.approx(8 / 9)


@TODO
def test_review_metrics():
    a = by_model()["a"]
    assert a["reviewed"] == 2
    assert a["edits_per_review"] == 1.0
    assert a["flag_dismissal_rate"] == 0.4  # 2 dismissed of 5 decided
    assert a["approval_rate"] == 0.5


@TODO
def test_review_metrics_are_none_without_reviews():
    b = by_model()["b"]
    assert b["reviewed"] == 0
    assert b["edits_per_review"] is None and b["flag_dismissal_rate"] is None and b["approval_rate"] is None
