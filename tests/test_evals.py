"""Eval plumbing: record/replay provider, spend cap, offline mode, flag metrics, gate."""

import json

import pytest

from apps.api.llm import LLMProvider, LLMResponse, Usage
from evals import recorder, run
from evals.metrics import flag_scores, percentile
from evals.recorder import BudgetExceeded, OfflineMiss, RecordingProvider


class Costly(LLMProvider):
    name, model = "fake", "fake-model"

    def __init__(self, cost=0.10):
        self.calls, self.cost = 0, cost

    def generate(self, prompt, images=(), json_mode=True):
        self.calls += 1
        return LLMResponse(f'{{"n": {self.calls}}}', Usage(1, 10, 5, 100.0, self.cost))


@pytest.fixture(autouse=True)
def tmp_recordings(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "RECORDINGS", tmp_path)


def make(inner, **kw):
    return RecordingProvider(inner, "m", "clean", **kw)


def test_records_then_replays_for_free():
    inner = Costly()
    rec = make(inner)
    rec.use("A/x.pdf")
    first = rec.generate("p")
    rec.save()
    again = make(Costly())  # fresh process
    again.use("A/x.pdf")
    assert again.generate("p").text == first.text and again.live_calls == 0 and again.replayed == 1


def test_only_missing_calls_hit_the_api():
    inner = Costly()
    rec = make(inner)
    rec.use("A/x.pdf")
    rec.generate("p")
    rec.save()
    rec2 = make(inner)
    rec2.use("A/x.pdf")
    rec2.generate("p")  # replayed
    rec2.generate("retry prompt")  # 2nd call for the same file was never recorded -> live
    assert inner.calls == 2 and rec2.live_calls == 1


def test_budget_cap_stops_before_overspending():
    rec = make(Costly(cost=0.10), budget_usd=0.15)
    rec.use("A/x.pdf")
    rec.generate("1")
    rec.generate("2")  # spent 0.10 < 0.15 -> allowed, now 0.20
    with pytest.raises(BudgetExceeded):
        rec.generate("3")


def test_offline_never_calls_the_api():
    with pytest.raises(OfflineMiss):
        make(None, offline=True)  # no recording file
    rec = make(Costly())
    rec.use("A/x.pdf")
    rec.generate("p")
    rec.save()
    off = make(None, offline=True)
    off.use("A/other.pdf")
    with pytest.raises(OfflineMiss):
        off.generate("p")


def test_changed_prompts_invalidate_recordings(tmp_path, monkeypatch):
    rec = make(Costly())
    rec.use("A/x.pdf")
    rec.generate("p")
    rec.save()
    monkeypatch.setattr(recorder, "PROMPTS_SHA", "different")
    with pytest.raises(OfflineMiss):
        make(None, offline=True)
    assert make(Costly()).store == {}  # online: stale recordings are ignored, will be re-recorded


def test_flag_scores():
    s = flag_scores([({"a", "b"}, {"a"}), ({"a"}, {"a", "c"}), (set(), set())])
    o = s["overall"]
    assert (o["tp"], o["fp"], o["fn"]) == (2, 1, 1)
    assert s["per_code"]["b"]["recall"] == 0.0 and s["per_code"]["c"]["precision"] == 0.0


def test_percentile():
    assert percentile([1, 2, 3, 4, 100], 0.5) == 3 and percentile([], 0.5) == 0.0


def result(variant="clean", acc=0.99, recall=0.95, precision=0.95):
    return {"model": "m", "variant": variant, "accuracy": acc, "flags": {"overall": {"recall": recall, "precision": precision}}}


def test_gate_passes_and_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "BASELINE", tmp_path / "baseline.json")
    assert run.gate([result(), result("noisy", acc=0.90)]) == []
    assert any("accuracy" in f for f in run.gate([result(acc=0.90)]))
    assert any("recall" in f for f in run.gate([result(recall=0.5)]))
    assert any("precision" in f for f in run.gate([result(precision=0.5)]))
    assert run.gate([result("noisy", precision=0.6)]) == []  # noisy precision: baseline-tracked, not an absolute target


def test_gate_catches_regression_below_targets_headroom(tmp_path, monkeypatch):
    b = tmp_path / "baseline.json"
    b.write_text(json.dumps({"m/clean": {"accuracy": 1.0, "recall": 1.0}}))
    monkeypatch.setattr(run, "BASELINE", b)
    fails = run.gate([result(acc=0.97)])  # above the 95% target but below the recorded baseline
    assert fails and "REGRESSION" in fails[0]
