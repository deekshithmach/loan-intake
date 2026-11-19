"""Pass + fail case for every rule, plus planted-anomaly recall/evidence on ground truth."""

import json
from pathlib import Path

import pytest

from apps.api.rules import REGISTRY, Docs, run_rules
from tests.test_schemas import PAYSTUB, STATEMENT, W2_FIELDS

ROOT = Path(__file__).resolve().parents[1]
TRUTHS = sorted((ROOT / "data" / "sample").glob("*/truth.json")) + \
    sorted((ROOT / "data" / "generated").glob("*/truth.json"))


def docs(paystub=None, w2=None, statement=None, **_) -> Docs:
    return Docs.from_data({k: v for k, v in
                           {"paystub": paystub or PAYSTUB, "w2": w2 or W2_FIELDS,
                            "statement": statement or STATEMENT}.items()})


def codes(d: Docs) -> set[str]:
    return {f.code for f in run_rules(d)}


# W2_FIELDS is a different employer than PAYSTUB in the fixtures; align it for a clean baseline
CLEAN_W2 = {**W2_FIELDS, "employer": PAYSTUB["employer"]}
CLEAN_STMT = {**STATEMENT, "transactions": [
    {"date": "2025-10-01", "description": "RENT PAYMENT", "amount": -186070, "balance": 223930},
    {"date": "2025-10-03", "description": "PAYROLL BARAJAS, DECKER AND COX", "amount": 306709, "balance": 530639},
]}


def clean() -> Docs:
    return docs(w2=CLEAN_W2, statement=CLEAN_STMT)


def test_clean_has_no_flags():
    assert codes(clean()) == set()


def test_every_rule_has_a_failing_case_below():
    tested = {"altered_totals", "statement_unreconciled", "overdrafts", "risky_transactions",
              "income_mismatch", "fake_employer", "missing_payroll_deposits"}
    assert {r.name for r in REGISTRY} == tested


def test_altered_totals():
    f = run_rules(docs(paystub={**PAYSTUB, "net": 307300}, w2=CLEAN_W2, statement=CLEAN_STMT))
    (flag,) = [x for x in f if x.code == "altered_totals"]
    assert flag.evidence[0].doc == "paystub" and flag.evidence[0].field == "net"


def test_statement_unreconciled():
    assert "statement_unreconciled" in codes(docs(w2=CLEAN_W2, statement={**CLEAN_STMT, "closing_balance": 1}))


def test_overdrafts():
    txns = CLEAN_STMT["transactions"] + [
        {"date": "2025-10-04", "description": "ONLINE TRANSFER OUT", "amount": -540000, "balance": -9361},
        {"date": "2025-10-04", "description": "OVERDRAFT FEE", "amount": -3500, "balance": -12861}]
    d = docs(w2=CLEAN_W2, statement={**CLEAN_STMT, "transactions": txns, "closing_balance": -12861})
    (flag,) = [x for x in run_rules(d) if x.code == "overdrafts"]
    assert flag.evidence[0].field == "transactions.2.balance"


def test_risky_transactions():
    txns = CLEAN_STMT["transactions"] + [
        {"date": "2025-10-05", "description": "DRAFTKINGS", "amount": -5000, "balance": 525639}]
    d = docs(w2=CLEAN_W2, statement={**CLEAN_STMT, "transactions": txns, "closing_balance": 525639})
    assert "risky_transactions" in codes(d)


def test_income_mismatch():
    assert "income_mismatch" in codes(docs(w2={**CLEAN_W2, "wages_box1": 13_000_000}, statement=CLEAN_STMT))


def test_income_within_tolerance():
    assert "income_mismatch" not in codes(docs(w2={**CLEAN_W2, "wages_box1": 11_000_000}, statement=CLEAN_STMT))


def test_fake_employer():
    assert "fake_employer" in codes(docs(w2={**CLEAN_W2, "employer": "PETERS PLC"}, statement=CLEAN_STMT))


def test_employer_suffix_and_punctuation_ignored():
    w2 = {**CLEAN_W2, "employer": "Barajas Decker & Cox, Inc."}
    assert "fake_employer" not in codes(docs(w2=w2, statement=CLEAN_STMT))


def test_missing_payroll_deposits():
    assert "missing_payroll_deposits" in codes(docs(w2=CLEAN_W2))  # STATEMENT payroll has no employer name


def test_rules_skip_missing_docs():
    assert run_rules(Docs.from_data({"paystub": PAYSTUB})) == []


@pytest.mark.skipif(not TRUTHS, reason="no generated data")
@pytest.mark.parametrize("path", TRUTHS, ids=lambda p: f"{p.parent.parent.name}/{p.parent.name}")
def test_planted_anomalies_flagged_with_evidence(path):
    t = json.loads(path.read_text())
    flags = run_rules(Docs.from_data({k: v["fields"] for k, v in t["documents"].items()}))
    assert {f.code for f in flags} == set(t["expected_flags"])  # recall AND precision
    by_code = {f.code: f for f in flags}
    for a in t["anomalies"]:  # evidence points at the planted doc + field
        assert any(e.doc == a["doc"] and e.field.split(".")[0] == a["field"] for e in by_code[a["code"]].evidence)
