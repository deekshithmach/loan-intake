"""All validation + cross-check rules. Flag codes match datagen anomaly codes."""

import re
from difflib import SequenceMatcher

from .engine import Docs, rule
from .flags import Evidence, Flag, Severity

INCOME_TOLERANCE = 0.10  # W-2 wages vs annualized pay-stub YTD
NAME_SIMILARITY = 0.85
RISKY = re.compile(r"\b(CASINO|DRAFTKINGS|FANDUEL|BETMGM|GAMBLING|CASH ADVANCE|PAYDAY LOAN)\b")
_SUFFIX = re.compile(r"\b(INC|LLC|LTD|CORP|CORPORATION|CO|PLC|GROUP|AND)\b")


def usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def norm_company(name: str) -> str:
    return " ".join(_SUFFIX.sub(" ", re.sub(r"[^A-Z0-9 ]", " ", name.upper())).split())


def same_company(a: str, b: str) -> bool:
    return SequenceMatcher(None, norm_company(a), norm_company(b)).ratio() >= NAME_SIMILARITY


# ---- validate: one document --------------------------------------------------
@rule("validate", "paystub")
def altered_totals(d: Docs) -> list[Flag]:
    p = d.paystub
    expected = p.gross - p.deductions.total
    if p.net == expected:
        return []
    ev = [Evidence(doc="paystub", field="net", value=p.net, note=f"gross - deductions = {usd(expected)}")]
    if d.statement:  # corroborate with actual payroll deposits
        ev += [Evidence(doc="statement", field=f"transactions.{i}.amount", value=t.amount, note="payroll deposit")
               for i, t in enumerate(d.statement.transactions) if t.description.startswith("PAYROLL")][:3]
    return [Flag(code="altered_totals", severity=Severity.HIGH, evidence=ev,
                 message=f"Net pay {usd(p.net)} != gross - deductions {usd(expected)} "
                         f"(off by {usd(p.net - expected)})")]


@rule("validate", "statement")
def statement_unreconciled(d: Docs) -> list[Flag]:
    s = d.statement
    if s.reconciles():
        return []
    computed = s.opening_balance + sum(t.amount for t in s.transactions)
    return [Flag(code="statement_unreconciled", severity=Severity.HIGH,
                 message=f"Opening + transactions = {usd(computed)}, statement says {usd(s.closing_balance)}",
                 evidence=[Evidence(doc="statement", field="closing_balance", value=s.closing_balance)])]


@rule("validate", "statement")
def overdrafts(d: Docs) -> list[Flag]:
    ev = [Evidence(doc="statement", field=f"transactions.{i}", value=t.amount,
                   note=f"{t.date} {t.description} → balance {usd(t.balance)}")
          for i, t in enumerate(d.statement.transactions)
          if "OVERDRAFT" in t.description.upper() or "NSF" in t.description.upper()]
    first_negative = next(((i, t) for i, t in enumerate(d.statement.transactions) if t.balance < 0), None)
    if first_negative:
        i, t = first_negative
        ev.insert(0, Evidence(doc="statement", field=f"transactions.{i}.balance", value=t.balance,
                              note=f"balance first negative on {t.date}"))
    if not ev:
        return []
    fees = sum(1 for e in ev if "OVERDRAFT" in e.note.upper() or "NSF" in e.note.upper())
    return [Flag(code="overdrafts", severity=Severity.MEDIUM, evidence=ev,
                 message=f"Account went negative; {fees} overdraft/NSF fee(s)")]


@rule("validate", "statement")
def risky_transactions(d: Docs) -> list[Flag]:
    ev = [Evidence(doc="statement", field=f"transactions.{i}", value=t.amount, note=f"{t.date} {t.description}")
          for i, t in enumerate(d.statement.transactions) if RISKY.search(t.description.upper())]
    return [Flag(code="risky_transactions", severity=Severity.MEDIUM, evidence=ev,
                 message=f"{len(ev)} gambling / cash-advance transaction(s)")] if ev else []


# ---- cross_check: several documents -----------------------------------------
@rule("cross_check", "paystub", "w2")
def income_mismatch(d: Docs) -> list[Flag]:
    p, w = d.paystub, d.w2
    if p.pay_date.year != w.year or p.ytd_gross == 0:
        return []
    annualized = round(p.ytd_gross * 365 / p.pay_date.timetuple().tm_yday)
    diff = (w.wages_box1 - annualized) / annualized
    if abs(diff) <= INCOME_TOLERANCE:
        return []
    return [Flag(code="income_mismatch", severity=Severity.HIGH,
                 message=f"W-2 wages {usd(w.wages_box1)} vs pay-stub annualized {usd(annualized)} ({diff:+.0%})",
                 evidence=[Evidence(doc="w2", field="wages_box1", value=w.wages_box1),
                           Evidence(doc="paystub", field="ytd_gross", value=p.ytd_gross,
                                    note=f"as of {p.pay_date}")])]


@rule("cross_check", "paystub", "w2")
def fake_employer(d: Docs) -> list[Flag]:
    p, w = d.paystub, d.w2
    if same_company(p.employer, w.employer):
        return []
    ev = [Evidence(doc="w2", field="employer", value=w.employer),
          Evidence(doc="paystub", field="employer", value=p.employer)]
    if d.statement:
        payroll = [(i, t) for i, t in enumerate(d.statement.transactions) if t.description.startswith("PAYROLL")]
        if payroll:
            i, t = payroll[0]
            ev.append(Evidence(doc="statement", field=f"transactions.{i}.description", value=t.description,
                               note="deposits come from the pay-stub employer"))
    return [Flag(code="fake_employer", severity=Severity.HIGH, evidence=ev,
                 message=f"W-2 employer '{w.employer}' does not match pay-stub employer '{p.employer}'")]


@rule("cross_check", "paystub", "statement")
def missing_payroll_deposits(d: Docs) -> list[Flag]:
    if any(same_company(t.description.removeprefix("PAYROLL "), d.paystub.employer)
           for t in d.statement.transactions if t.amount > 0):
        return []
    return [Flag(code="missing_payroll_deposits", severity=Severity.MEDIUM,
                 message=f"No deposits from '{d.paystub.employer}' on the bank statement",
                 evidence=[Evidence(doc="paystub", field="employer", value=d.paystub.employer)])]
