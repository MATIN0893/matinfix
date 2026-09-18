from __future__ import annotations

import asyncio
import csv
import io
import time
import urllib.request
from dataclasses import dataclass

from app.pricing.engine import ServiceKind, detect_service, normalize_brand, normalize_text


@dataclass(frozen=True)
class SheetPriceRow:
    brand: str
    model: str
    service: str
    price_rub: int


class GoogleSheetsPriceProvider:
    source = "google_sheets"

    def __init__(self, csv_url: str | None, ttl_seconds: int = 300) -> None:
        self.csv_url = csv_url.strip() if csv_url else ""
        self.ttl_seconds = ttl_seconds
        self._rows: list[SheetPriceRow] = []
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def find(self, brand: str, model: str, service: str) -> int | None:
        if not self.csv_url:
            return None
        await self._refresh_if_needed()
        wanted_brand = normalize_brand(brand)
        wanted_model = normalize_text(model)
        wanted_service = service if isinstance(service, ServiceKind) else detect_service(service)
        for row in self._rows:
            if normalize_brand(row.brand) != wanted_brand:
                continue
            if normalize_text(row.model) != wanted_model:
                continue
            if detect_service(row.service) is wanted_service:
                return row.price_rub
        return None

    async def _refresh_if_needed(self) -> None:
        if self._rows and time.monotonic() - self._loaded_at < self.ttl_seconds:
            return
        async with self._lock:
            if self._rows and time.monotonic() - self._loaded_at < self.ttl_seconds:
                return
            try:
                payload = await asyncio.to_thread(self._download)
                self._rows = self._parse(payload)
                self._loaded_at = time.monotonic()
            except Exception:
                # A temporary Sheets/network failure must fall back to the built-in catalog.
                self._loaded_at = time.monotonic()

    def _download(self) -> str:
        request = urllib.request.Request(
            self.csv_url,
            headers={"User-Agent": "MATINFIX-price-provider/1.0"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8-sig")

    @staticmethod
    def _parse(payload: str) -> list[SheetPriceRow]:
        reader = csv.DictReader(io.StringIO(payload))
        rows: list[SheetPriceRow] = []
        for raw in reader:
            brand = (raw.get("Бренд") or raw.get("Brand") or "").strip()
            model = (raw.get("Модель") or raw.get("Model") or "").strip()
            service = (raw.get("Услуга") or raw.get("Service") or "").strip()
            price_text = (raw.get("Цена") or raw.get("Price") or "").strip()
            if not brand or not model or not service or not price_text:
                continue
            try:
                price = int(float(price_text.replace(" ", "").replace(",", ".")))
            except ValueError:
                continue
            if price >= 0:
                rows.append(SheetPriceRow(brand, model, service, price))
        return rows
