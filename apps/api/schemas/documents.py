"""Pydantic schemas for the three document types.

Field names must match `truth.json` (see data/sample/*/truth.json) so evals can
compare extracted output to ground truth key by key.

Design rule: a schema checks *shape* (types, formats, things that are impossible).
It does NOT check *business truth*: a pay stub whose net doesn't equal
gross - deductions is a valid PayStub. Catching that is a Stage 3 rule and
produces a risk flag. If the schema rejected it, the anomaly would vanish.
"""

import datetime as dt  # `date: date` inside a class shadows the type, so alias the module
from typing import Annotated

from pydantic import Field, model_validator

from .common import Money, StrictModel

NonNegMoney = Annotated[Money, Field(ge=0)]
Text = Annotated[str, Field(min_length=1)]


class Transaction(StrictModel):
    date: dt.date
    description: Text
    amount: Money = Field(description="signed: positive = deposit, negative = withdrawal")
    balance: Money = Field(description="running balance after this transaction (may be negative)")


class Deductions(StrictModel):
    federal_tax: NonNegMoney
    social_security: NonNegMoney
    medicare: NonNegMoney
    state_tax: NonNegMoney
    health_insurance: NonNegMoney

    @property
    def total(self) -> int:
        return sum(getattr(self, name) for name in type(self).model_fields)


class PayStub(StrictModel):
    employer: Text
    employee: Text
    pay_period_start: dt.date
    pay_period_end: dt.date
    pay_date: dt.date
    gross: NonNegMoney = Field(description="current-period gross pay")
    net: NonNegMoney = Field(description="current-period net pay")
    ytd_gross: NonNegMoney = Field(description="year-to-date gross pay")
    deductions: Deductions = Field(description="current-period amounts")

    @model_validator(mode="after")
    def _check(self) -> "PayStub":
        if self.pay_period_end < self.pay_period_start:
            raise ValueError("pay_period_end is before pay_period_start")
        if self.net > self.gross:
            raise ValueError("net exceeds gross")
        return self


class W2(StrictModel):
    employer: Text
    ein: str = Field(pattern=r"^\d{2}-\d{7}$", description='e.g. "57-4647485"')
    employee: Text
    ssn: str = Field(pattern=r"^\d{3}-\d{2}-\d{4}$", description='e.g. "950-49-2539"')
    year: int = Field(ge=2000, le=2100)
    wages_box1: NonNegMoney
    federal_tax_box2: NonNegMoney
    ss_wages_box3: NonNegMoney
    ss_tax_box4: NonNegMoney
    medicare_wages_box5: NonNegMoney
    medicare_tax_box6: NonNegMoney


class BankStatement(StrictModel):
    bank: Text
    account_holder: Text
    account_last4: str = Field(pattern=r"^\d{4}$", description="last 4 digits of the account number")
    period_start: dt.date
    period_end: dt.date
    opening_balance: Money
    transactions: list[Transaction] = Field(description="every row, in printed order")
    closing_balance: Money

    @model_validator(mode="after")
    def _check(self) -> "BankStatement":
        if self.period_end < self.period_start:
            raise ValueError("period_end is before period_start")
        return self

    def reconciles(self) -> bool:
        """opening + sum(amounts) == closing. False is a flag, not an error."""
        return self.opening_balance + sum(t.amount for t in self.transactions) == self.closing_balance
