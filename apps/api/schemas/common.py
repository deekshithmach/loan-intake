"""Shared types used by every document schema."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, WithJsonSchema


class DocType(StrEnum):
    PAYSTUB = "paystub"
    W2 = "w2"
    STATEMENT = "statement"
    UNKNOWN = "unknown"


class StrictModel(BaseModel):
    """Base for all extracted documents: unknown keys are errors, strings are trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def to_cents(value: object) -> int:
    """Convert a money value into integer cents.

    Contract: **strings and floats are dollars, ints are already cents.**
    (LLMs return dollars as text; truth.json and our own code use int cents.)

        "$4,115.38" -> 411538      "(12.50)" -> -1250  (accounting negative)
        "4,115"     -> 411500      "-12.50"  -> -1250
        4115.38     -> 411538      411538    -> 411538 (int passes through)

    Raise ValueError (not TypeError: pydantic only converts ValueError into a
    ValidationError) for: None, bool, "", non-numeric text, >2 decimal places
    in a string ("12.345").

    """
    # bool first: isinstance(True, int) is True, so the int branch would accept it.
    if value is None or isinstance(value, bool):
        raise ValueError(f"not a money value: {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        try:  # str() first so Decimal sees 4115.38, not 4115.37999999...
            return int((Decimal(str(value)) * 100).quantize(Decimal(1), ROUND_HALF_UP))
        except InvalidOperation as e:  # nan / inf
            raise ValueError(f"not a money value: {value!r}") from e
    if isinstance(value, str):
        s = value.strip()
        negative = s.startswith("(") and s.endswith(")")
        if negative:
            s = s[1:-1]
        s = s.replace("$", "").replace(",", "").replace(" ", "")
        m = _DOLLARS.fullmatch(s)
        if not m:
            raise ValueError(f"not a money value: {value!r}")
        sign, whole, frac = m.groups()
        cents = int(whole) * 100 + int((frac or "").ljust(2, "0"))
        return -cents if negative != bool(sign) else cents
    raise ValueError(f"unsupported money type: {type(value).__name__}")


_DOLLARS = re.compile(r"(-?)(\d+)(?:\.(\d{1,2}))?")

# Use as a field type: `gross: Money`. Validation runs to_cents first, then checks int.
# The JSON schema says "string" because that's what we ask the LLM to return.
Money = Annotated[
    int,
    BeforeValidator(to_cents),
    WithJsonSchema({"type": "string", "description": 'US dollars as printed, e.g. "4,115.38"'}),
]
