import json

from apps.api.schemas import SCHEMAS, DocType

CLASSIFY = """You are classifying a US loan-application document.
Answer with JSON only: {"doc_type": "<paystub|w2|statement|unknown>"}
- paystub: an employee earnings statement for one pay period
- w2: IRS Form W-2 Wage and Tax Statement
- statement: a bank account statement listing transactions
"""

EXTRACT = """Extract the fields of this {label} into JSON matching this JSON Schema:
{schema}

Rules:
- Return JSON only, with exactly the schema's keys. No extra keys, no commentary.
- Money: the amount as printed, as a string, e.g. "4,115.38". Negative amounts: "-12.50".
- Dates: YYYY-MM-DD.
- Names, employers, banks: copy exactly as printed.
- Copy values as printed even if they look inconsistent; do not fix or recompute them.
{extra}
{source}"""

LABELS = {DocType.PAYSTUB: "pay stub", DocType.W2: "Form W-2", DocType.STATEMENT: "bank statement"}
EXTRA = {
    DocType.STATEMENT: "- Include every transaction row in order. Withdrawals are negative amounts.",
    DocType.PAYSTUB: "- gross, net and deductions are CURRENT-period amounts, not year-to-date.",
}

RETRY = """

Your previous answer failed validation:
{error}

Previous answer:
{previous}

Return the corrected JSON only."""


def extract_prompt(doc_type: DocType, text: str | None) -> str:
    schema = json.dumps(SCHEMAS[doc_type].model_json_schema(), indent=1)
    source = f"Document text:\n---\n{text}\n---" if text else "The document is in the attached page image(s)."
    return EXTRACT.format(label=LABELS[doc_type], schema=schema, extra=EXTRA.get(doc_type, ""), source=source)
