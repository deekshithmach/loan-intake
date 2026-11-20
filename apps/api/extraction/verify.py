"""Arithmetic self-check for SCANNED bank statements. A misread digit on a blurry scan breaks the running balance;
we re-read once with a pointer to the failing row. The re-read replaces the first answer only if it fixes the math.

Deliberately NOT applied to text PDFs (their numbers are exact, so a mismatch is the document's own truth) nor to
pay-stub totals: in evals the model "fixed" a genuinely altered net pay to make it add up, hiding the fraud."""

from apps.api.schemas import BankStatement, DocType

VERIFY = """

A consistency check on your previous answer found a problem:
{problem}

Look at the document again, paying close attention to the digits mentioned above (the scan may be blurry).
Fix any value you misread. The document itself may genuinely not add up: if so, report exactly what is printed
and never change a number just to make the totals work.

Previous answer:
{previous}

Return the corrected JSON only."""


def arithmetic_problem(doc_type: DocType, model) -> str | None:
    if doc_type is DocType.STATEMENT and isinstance(model, BankStatement) and not model.reconciles():
        prev, bad = model.opening_balance, []
        for i, t in enumerate(model.transactions):
            if prev + t.amount != t.balance:
                bad.append(f"row {i + 1} ({t.date} {t.description}): previous balance {prev / 100:,.2f} + amount "
                           f"{t.amount / 100:,.2f} != balance {t.balance / 100:,.2f}")
            prev = t.balance
        where = "; ".join(bad[:4]) or "a transaction amount or the closing balance"
        return f"opening balance + transactions does not equal the closing balance. Check: {where}"
    return None
