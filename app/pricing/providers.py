from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PriceRecord:
    brand: str
    model: str
    service: str
    price_rub: int
    source: str


class PriceProvider(Protocol):
    async def find(self, brand: str, model: str, service: str) -> PriceRecord | None: ...


class StaticCatalogProvider:
    """Adapter used by tests/dev; Google Sheets can be plugged in later without changing the engine."""

    def __init__(self, records: list[PriceRecord] | None = None) -> None:
        self._records = records or []

    async def find(self, brand: str, model: str, service: str) -> PriceRecord | None:
        key = (brand.lower().strip(), model.lower().strip(), service.lower().strip())
        for record in self._records:
            if (record.brand.lower().strip(), record.model.lower().strip(), record.service.lower().strip()) == key:
                return record
        return None
