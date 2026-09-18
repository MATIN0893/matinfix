import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.api.master import require_master_key
from app.main import app
from app.notifications import (
    customer_status_keyboard,
    customer_status_message,
    new_repair_keyboard,
    new_repair_message,
    public_repair_url,
    review_message,
)


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "matinfix", "version": "0.2.0"}


@pytest.mark.asyncio
async def test_website_cors_preflight() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/crm/repairs",
            headers={
                "Origin": "https://matinfix-dtceinuc.manus.space",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://matinfix-dtceinuc.manus.space"


def test_new_repair_notification_contains_public_link_data() -> None:
    class RepairStub:
        id = "12345678-aaaa-bbbb-cccc-dddddddddddd"
        public_token = "public-token"
        brand = "Xiaomi"
        model = "Redmi Note"
        problem = "Замена дисплея"

    repair = RepairStub()
    assert "Xiaomi Redmi Note" in new_repair_message(repair)
    assert public_repair_url(repair).endswith("/?order=public-token")
    callbacks = [button.callback_data for row in new_repair_keyboard(repair).inline_keyboard[1:] for button in row]
    assert "repair_status:12345678-aaaa-bbbb-cccc-dddddddddddd:ready" in callbacks
    repair.status = "repairing"
    assert "В ремонте" in customer_status_message(repair, "Поставили новый дисплей")
    assert customer_status_keyboard(repair).inline_keyboard[0][0].url.endswith("public-token")
    review = type("ReviewStub", (), {"rating": 4, "comment": "Всё отлично"})()
    assert "★★★★☆" in review_message(repair, review)
    assert "Всё отлично" in review_message(repair, review)


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


@pytest.mark.asyncio
async def test_master_api_rejects_invalid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "master_api_key", "test-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/master/orders/status",
            json={"workspace_id": "workspace-a", "repair_id": "missing", "status": "ready"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_master_api_allows_request_with_valid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "master_api_key", "test-secret")
    assert require_master_key("test-secret") is None
