import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "matinfix", "version": "0.2.0"}


@pytest.mark.asyncio
async def test_architecture() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/system/architecture")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "MATIN"
    assert payload["ai_core"]["agents"] == ["customer", "master", "admin"]
    assert payload["services"] == ["price", "stock", "crm", "accounting", "knowledge"]


@pytest.mark.asyncio
async def test_budget_phone_display_price() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/price",
            json={"brand": "Xiaomi", "model": "Redmi 9", "service": "замена дисплея", "model_year": 2020},
        )
    assert response.status_code == 200
    assert response.json()["price_rub"] == 1500


@pytest.mark.asyncio
async def test_unknown_iphone_goes_to_master() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/price",
            json={"brand": "iPhone", "model": "15 Pro", "service": "замена дисплея"},
        )
    assert response.status_code == 200
    assert response.json()["needs_master"] is True
    assert response.json()["price_rub"] is None
