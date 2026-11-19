import pymupdf
import pytest

from datagen.generate import generate
from datagen.profiles import PERIODS, build_applicant

APPS = [build_applicant(i, 42) for i in range(60)]
CLEAN = [a for a in APPS if not a["anomalies"]]


def F(a, doc):
    return a["documents"][doc]["fields"]


def test_deterministic():
    assert build_applicant(3, 42) == build_applicant(3, 42)


@pytest.mark.parametrize("a", CLEAN, ids=lambda a: a["applicant_id"])
def test_clean_math(a):
    s, w, st = F(a, "paystub"), F(a, "w2"), F(a, "statement")
    assert s["gross"] - sum(s["deductions"].values()) == s["net"]
    assert s["ytd_gross"] == s["gross"] * PERIODS == w["wages_box1"]
    assert s["employer"] == w["employer"]
    bal = st["opening_balance"]
    for t in st["transactions"]:
        bal += t["amount"]
        assert t["balance"] == bal
    assert bal == st["closing_balance"]
    assert min(t["balance"] for t in st["transactions"]) >= 0
    deposits = [t["amount"] for t in st["transactions"] if t["description"].startswith("PAYROLL")]
    assert deposits and set(deposits) == {s["net"]}


def test_anomalies_planted_and_consistent():
    flagged = [a for a in APPS if a["anomalies"]]
    assert 0.25 < len(flagged) / len(APPS) < 0.55
    for a in flagged:
        s, w, st = F(a, "paystub"), F(a, "w2"), F(a, "statement")
        for an in a["anomalies"]:
            if an["code"] == "income_mismatch":
                assert w["wages_box1"] != s["ytd_gross"]
            if an["code"] == "fake_employer":
                assert w["employer"] != s["employer"]
            if an["code"] == "altered_totals":
                assert s["gross"] - sum(s["deductions"].values()) != s["net"]
            if an["code"] == "overdrafts":
                assert min(t["balance"] for t in st["transactions"]) < 0
                assert any(t["description"] == "OVERDRAFT FEE" for t in st["transactions"])
        assert a["expected_flags"] == sorted({x["code"] for x in a["anomalies"]})


def test_pdfs_and_scans(tmp_path):
    res = generate(8, tmp_path, seed=7)
    scanned = 0
    for t in res:
        for doc in t["documents"].values():
            page = pymupdf.open(tmp_path / t["applicant_id"] / doc["file"])[0]
            if doc["scanned"]:
                scanned += 1
                assert page.get_text().strip() == "" and page.get_images()
            else:
                assert page.get_text().strip()
    assert scanned > 0
