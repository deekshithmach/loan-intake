"""PII masking for logs and audit details. Logs carry ids, never raw SSNs/account numbers."""

import logging
import re
from typing import Any

_SSN = re.compile(r"\b\d{3}-\d{2}-(\d{4})\b")
_SSN_BARE = re.compile(r"(?<![\d-])\d{5}(\d{4})(?![\d-])")  # 9 digits, no dashes
_ACCOUNT = re.compile(r"\b\d{6,}(\d{4})\b")  # long account / card numbers (10+ digits)
PII_KEYS = {"ssn", "account_number"}


def mask_text(text: str) -> str:
    text = _SSN.sub(r"***-**-\1", text)
    text = _ACCOUNT.sub(r"****\1", text)
    return _SSN_BARE.sub(r"*****\1", text)


def mask_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return {k: mask_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_value(key, v) for v in value]
    if isinstance(value, str):
        return f"***{value[-4:]}" if key.split(".")[-1] in PII_KEYS else mask_text(value)
    return value


class PiiFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_text(record.getMessage())
        record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for h in logging.getLogger().handlers:
        if not any(isinstance(f, PiiFilter) for f in h.filters):
            h.addFilter(PiiFilter())
