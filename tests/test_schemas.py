"""Spec for apps/api/schemas. Make these pass."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.schemas import (
    SCHEMAS,
    W2,
    BankStatement,
    DocType,
    PayStub,
    Transaction,
    to_cents,
)

ROOT = Path(__file__).resolve().parents[1]
TRUTHS = sorted((ROOT / "data" / "sample").glob("*/truth.json"))

PAYSTUB = {
    "employer": "BARAJAS, DECKER AND COX", "employee": "SANDRA DAVIS",
    "pay_period_start": "2025-12-13", "pay_period_end": "2025-12-26", "pay_date": "2025-12-26",
    "gross": 411538, "net": 306709, "ytd_gross": 10699988,
    "deductions": {"federal_tax": 49385, "social_security": 25515, "medicare": 5967,
                   "state_tax": 16462, "health_insurance": 7500},
}
W2_FIELDS = {
    "employer": "PETERS PLC", "ein": "57-4647485", "employee": "SANDRA DAVIS",
    "ssn": "950-49-2539", "year": 2025, "wages_box1": 10699988, "federal_tax_box2": 1284010,
    "ss_wages_box3": 10699988, "ss_tax_box4": 663390,
    "medicare_wages_box5": 10699988, "medicare_tax_box6": 155142,
}
STATEMENT = {
    "bank": "First Meridian Bank", "account_holder": "SANDRA DAVIS", "account_last4": "8251",
    "period_start": "2025-10-01", "period_end": "2025-12-31", "opening_balance": 410000,
    "transactions": [
        {"date": "2025-10-01", "description": "RENT PAYMENT", "amount": -186070, "balance": 223930},
        {"date": "2025-10-03", "description": "PAYROLL", "amount": 306709, "balance": 530639},
    ],
    "closing_balance": 530639,
}


def with_(base: dict, **changes) -> dict:
    return {**base, **changes}


# ---- to_cents ---------------------------------------------------------------
@pytest.mark.parametrize("raw, cents", [
    ("$4,115.38", 411538), ("4115.38", 411538), ("4,115", 411500), (" $0.07 ", 7),
    ("-12.50", -1250), ("(12.50)", -1250), ("$1,234.5", 123450),
    (4115.38, 411538), (0.1 + 0.2, 30),  # float noise must round, not truncate
    (411538, 411538), (0, 0),  # ints are already cents
])
def test_to_cents(raw, cents):
    assert to_cents(raw) == cents
    assert type(to_cents(raw)) is int


@pytest.mark.parametrize("bad", [None, True, "", "abc", "12.345", "$"])
def test_to_cents_rejects(bad):
    with pytest.raises(ValueError):
        to_cents(bad)


# ---- PayStub ----------------------------------------------------------------
def test_paystub_valid():
    p = PayStub.model_validate(PAYSTUB)
    assert p.pay_period_end.isoformat() == "2025-12-26"
    assert p.deductions.total == 104829


def test_paystub_money_from_llm_strings():
    assert PayStub.model_validate(with_(PAYSTUB, gross="$4,115.38")).gross == 411538


def test_paystub_allows_altered_totals():
    # net != gross - deductions is an ANOMALY to flag later, not a schema error
    PayStub.model_validate(with_(PAYSTUB, net=307000))


@pytest.mark.parametrize("changes", [
    {"pay_period_end": "2025-12-01"},  # before start
    {"net": 500000},  # net > gross
    {"gross": -1},
    {"surprise": "x"},  # extra keys forbidden
])
def test_paystub_rejects(changes):
    with pytest.raises(ValidationError):
        PayStub.model_validate(with_(PAYSTUB, **changes))


def test_paystub_rejects_missing_field():
    with pytest.raises(ValidationError):
        PayStub.model_validate({k: v for k, v in PAYSTUB.items() if k != "employer"})


# ---- W2 ---------------------------------------------------------------------
def test_w2_valid():
    assert W2.model_validate(W2_FIELDS).wages_box1 == 10699988


@pytest.mark.parametrize("changes", [
    {"ein": "574647485"}, {"ssn": "950492539"}, {"ssn": "950-49-253"},
    {"year": 1999}, {"year": 2101}, {"wages_box1": -5},
])
def test_w2_rejects(changes):
    with pytest.raises(ValidationError):
        W2.model_validate(with_(W2_FIELDS, **changes))


# ---- BankStatement ----------------------------------------------------------
def test_statement_valid_and_reconciles():
    s = BankStatement.model_validate(STATEMENT)
    assert isinstance(s.transactions[0], Transaction)
    assert s.reconciles() is True


def test_statement_tampered_closing_is_valid_but_does_not_reconcile():
    s = BankStatement.model_validate(with_(STATEMENT, closing_balance=530640))
    assert s.reconciles() is False


def test_statement_allows_negative_balances():
    BankStatement.model_validate(with_(STATEMENT, opening_balance=-5000, closing_balance=115639))


@pytest.mark.parametrize("changes", [
    {"account_last4": "825"}, {"account_last4": "82a1"}, {"period_end": "2025-09-30"},
])
def test_statement_rejects(changes):
    with pytest.raises(ValidationError):
        BankStatement.model_validate(with_(STATEMENT, **changes))


# ---- Every committed sample's ground truth must fit the schemas -------------
@pytest.mark.skipif(not TRUTHS, reason="no data/sample")
@pytest.mark.parametrize("truth_path", TRUTHS, ids=lambda p: p.parent.name)
def test_truth_fits_schemas(truth_path):
    docs = json.loads(truth_path.read_text())["documents"]
    for doc_type, doc in docs.items():
        model = SCHEMAS[DocType(doc_type)].model_validate(doc["fields"])
        if isinstance(model, BankStatement):
            assert model.reconciles()
