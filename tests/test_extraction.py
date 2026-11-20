"""Offline tests: a scripted FakeProvider stands in for the LLM."""

import json
from pathlib import Path

import pytest

from apps.api.extraction import Extractor, classify_rules, load_pdf
from apps.api.llm import LLMProvider, LLMResponse, Usage
from apps.api.schemas import DocType
from evals.compare import score
from tests.test_schemas import W2_FIELDS

ROOT = Path(__file__).resolve().parents[1]
TRUTHS = sorted((ROOT / "data" / "sample").glob("*/truth.json"))
DOCS = [(t.parent / d["file"], DocType(k), d["scanned"])
        for t in TRUTHS for k, d in json.loads(t.read_text())["documents"].items()]
TEXT_W2 = next((p for p, t, s in DOCS if t is DocType.W2 and not s), None)


class FakeProvider(LLMProvider):
    name, model = "fake", "fake"

    def __init__(self, *replies: str):
        self.replies, self.prompts = list(replies), []

    def generate(self, prompt, images=(), json_mode=True):
        self.prompts.append(prompt)
        return LLMResponse(self.replies.pop(0), Usage(1, 100, 50, 10.0, 0.001))


DOLLARS_W2 = json.dumps({**W2_FIELDS, "wages_box1": "106,999.88"})


@pytest.mark.parametrize("path, doc_type, scanned", DOCS, ids=lambda x: getattr(x, "name", str(x)))
def test_pdf_loading_and_rules(path, doc_type, scanned):
    c = load_pdf(path)
    assert c.scanned == scanned
    assert bool(c.images) == scanned
    if not scanned:
        assert classify_rules(c.text) is doc_type


@pytest.mark.skipif(TEXT_W2 is None, reason="no text W-2 in sample")
def test_retry_then_success():
    fake = FakeProvider("not json", f"```json\n{DOLLARS_W2}\n```")
    r = Extractor(fake).run(TEXT_W2)
    assert r.ok and r.attempts == 2 and r.data["wages_box1"] == 10699988
    assert "failed validation" in fake.prompts[1]  # error fed back
    assert r.usage.calls == 2 and r.usage.cost_usd == pytest.approx(0.002)


@pytest.mark.skipif(TEXT_W2 is None, reason="no text W-2 in sample")
def test_bad_output_fails_gracefully():
    bad = json.dumps({**W2_FIELDS, "ssn": "nope"})
    r = Extractor(FakeProvider(bad, bad)).run(TEXT_W2)
    assert not r.ok and r.data is None and "ssn" in r.error and r.attempts == 2


def test_classify_rules_ambiguous():
    assert classify_rules("hello world") is None


def test_score():
    truth = {"a": "X  y", "n": {"b": 1}, "t": [{"c": 2}]}
    assert all(score({"a": "x Y", "n": {"b": 1}, "t": [{"c": 2}]}, truth).values())
    assert score(None, truth) == {"a": False, "n.b": False, "t.0.c": False}


def test_usage_pricing():
    u = Usage.priced("gemini-2.5-flash", 1_000_000, 1_000_000, 5)
    assert u.cost_usd == pytest.approx(2.80)


# ---- arithmetic self-check (scanned statements only) ---------------------------------------
STMT = next(((p, json.loads(t.read_text())["documents"]["statement"]["fields"]) for t in TRUTHS
             for p, ty, sc in DOCS if ty is DocType.STATEMENT and sc and p.parent == t.parent), None)
CLASSIFIED = json.dumps({"doc_type": "statement"})


def _misread(fields: dict) -> dict:
    bad = json.loads(json.dumps(fields))
    bad["transactions"][1]["amount"] += 700  # one digit misread on a blurry scan -> balances stop adding up
    return bad


@pytest.mark.skipif(STMT is None, reason="no scanned statement in sample")
def test_misread_digit_triggers_one_reread_that_fixes_it():
    path, good = STMT
    fake = FakeProvider(CLASSIFIED, json.dumps(_misread(good)), json.dumps(good))
    r = Extractor(fake).run(path)
    assert r.ok and r.attempts == 2 and r.data["transactions"][1]["amount"] == good["transactions"][1]["amount"]
    assert "consistency check" in fake.prompts[2] and "row 2" in fake.prompts[2]


@pytest.mark.skipif(STMT is None, reason="no scanned statement in sample")
def test_reread_that_still_does_not_add_up_keeps_the_original():
    """A genuinely altered document must stay flaggable: never 'fix' numbers to make them add up."""
    path, good = STMT
    first, second = _misread(good), _misread(good)
    second["transactions"][1]["amount"] += 1
    r = Extractor(FakeProvider(CLASSIFIED, json.dumps(first), json.dumps(second))).run(path)
    assert r.ok and r.data["transactions"][1]["amount"] == first["transactions"][1]["amount"]


@pytest.mark.skipif(STMT is None, reason="no scanned statement in sample")
def test_consistent_document_costs_no_extra_call():
    path, good = STMT
    fake = FakeProvider(CLASSIFIED, json.dumps(good))
    assert Extractor(fake).run(path).attempts == 1 and len(fake.prompts) == 2  # classify + extract
