from .common import DocType, Money, StrictModel, to_cents
from .documents import W2, BankStatement, Deductions, PayStub, Transaction

SCHEMAS: dict[DocType, type[StrictModel]] = {
    DocType.PAYSTUB: PayStub,
    DocType.W2: W2,
    DocType.STATEMENT: BankStatement,
}

__all__ = [
    "SCHEMAS",
    "W2",
    "BankStatement",
    "Deductions",
    "DocType",
    "Money",
    "PayStub",
    "StrictModel",
    "Transaction",
    "to_cents",
]
