from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Evidence(BaseModel):
    doc: str  # paystub | w2 | statement
    field: str  # dotted path, e.g. "net", "transactions.41.balance"
    value: Any = None
    note: str = ""


class Flag(BaseModel):
    code: str
    severity: Severity
    message: str
    evidence: list[Evidence] = Field(default_factory=list)
