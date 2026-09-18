import pytest

from app.pricing.engine import PriceEngine
from app.pricing.google_sheets import GoogleSheetsPriceProvider, GoogleSheetsReballProvider


@pytest.mark.asyncio
async def test_repair_sheet_provider_uses_mock_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    csv_payload = """Бренд,Модель,Услуга,Цена
Iphone,iPhone 13 / 13 mini,Замена экрана (дисплея),3200
Iphone,iPhone 13 / 13 mini,Замена АКБ (аккумулятора),1200
"""
    provider = GoogleSheetsPriceProvider("https://example.invalid/repair.csv")
    monkeypatch.setattr(provider, "_download", lambda: csv_payload)

    engine = PriceEngine((provider,))
    display = await engine.decide("Iphone", "iPhone 13", "замена дисплея")
    battery = await engine.decide("Iphone", "iPhone 13 mini", "замена аккумулятора")

    assert display.price_rub == 3200
    assert display.source == "google_sheets"
    assert battery.price_rub == 1200
    assert battery.source == "google_sheets"


@pytest.mark.asyncio
async def test_reball_sheet_provider_uses_retail_price_from_mock_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_payload = """,,,,
,,, ,
Модель,,Опт,,РРЦ
,,, ,
SM-S911B/ Galaxy S23,,11000,,16500
SM-S938B/ Galaxy S25 Ultra,,18000,,27000
"""
    provider = GoogleSheetsReballProvider("https://example.invalid/reball.csv")
    monkeypatch.setattr(provider, "_download", lambda: csv_payload)

    engine = PriceEngine((provider,))
    by_code = await engine.decide("Samsung", "SM-S911B", "ребол платы")
    by_name = await engine.decide("Samsung", "Galaxy S23", "reball")
    unknown = await engine.decide("Samsung", "SM-UNKNOWN", "ребол платы")

    assert by_code.price_rub == 16500
    assert by_code.source == "google_sheets_reball"
    assert by_name.price_rub == 16500
    assert by_name.source == "google_sheets_reball"
    assert unknown.price_rub is None
    assert unknown.needs_master is True


@pytest.mark.asyncio
async def test_reball_provider_does_not_handle_other_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GoogleSheetsReballProvider("https://example.invalid/reball.csv")
    monkeypatch.setattr(provider, "_download", lambda: "Модель,,Опт,,РРЦ\nSM-S911B,,11000,,16500\n")

    assert await provider.find("Samsung", "SM-S911B", "display") is None
