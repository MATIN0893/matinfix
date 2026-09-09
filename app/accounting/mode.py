from __future__ import annotations

from datetime import date
from decimal import Decimal
from dataclasses import dataclass


ACCOUNTANT_CODEWORD = "NSS"


@dataclass(frozen=True)
class LedgerEntry:
    kind: str
    amount: Decimal
    description: str = ""
    day: date = date.today()


class AccountantMode:
    """Privacy boundary: accountant data is never exposed outside the exact NSS command."""

    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []

    def handle(self, text: str) -> str | None:
        if text.strip() == ACCOUNTANT_CODEWORD:
            return self.report()
        lower = text.lower()
        if any(x in lower for x in ("приход", "доход", "расход", "чек")):
            return "Принял"
        return None

    def report(self) -> str:
        today = date.today()
        income = sum((e.amount for e in self.entries if e.kind == "income"), Decimal(0))
        expenses = sum((e.amount for e in self.entries if e.kind == "expense"), Decimal(0))
        balance = income - expenses
        return f"БУХГАЛТЕР тут\n{today:%d %m %Y}\nДоход: {income:.2f} ₽\nРасход: {expenses:.2f} ₽\nКасса: {balance:.2f} ₽"
