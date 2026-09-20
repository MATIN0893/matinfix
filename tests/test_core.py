import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.api.master import require_master_key
from app.db.models import Base, RepairReview
from app.db.session import get_session
from app.main import app
from app.notifications import (
    customer_status_keyboard,
    customer_status_message,
    customer_review_keyboard,
    customer_review_message,
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
async def test_root() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


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
    assert "Как вам ремонт" in customer_review_message(repair)
    assert customer_review_keyboard(repair).inline_keyboard[0][0].url.endswith("public-token")


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


@pytest.mark.asyncio
async def test_public_review_flow_requires_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post(
                "/api/v1/crm/repairs",
                json={"workspace_id": "telegram-default", "brand": "Apple", "model": "iPhone 13", "problem": "screen"},
            )
            assert created.status_code == 201
            token = created.json()["public_token"]
            public_before = await client.get(f"/api/v1/crm/public/repairs/{token}")
            assert public_before.status_code == 200
            assert public_before.json()["status"] == "new"
            assert public_before.json()["can_review"] is False
            blocked = await client.post(f"/api/v1/crm/public/repairs/{token}/review", json={"rating": 5, "comment": "Отлично"})
            assert blocked.status_code == 400
            updating = await client.patch(
                f"/api/v1/crm/repairs/{created.json()['id']}/status",
                json={"workspace_id": "telegram-default", "status": "repairing", "comment": "Проверяем плату", "photo_file_id": "telegram-photo-id"},
            )
            assert updating.status_code == 200
            public_repairing = await client.get(f"/api/v1/crm/public/repairs/{token}")
            assert public_repairing.json()["status"] == "repairing"
            assert public_repairing.json()["history"][-1]["comment"] == "Проверяем плату"
            assert public_repairing.json()["history"][-1]["photo_file_id"] == "telegram-photo-id"
            ready = await client.patch(
                f"/api/v1/crm/repairs/{created.json()['id']}/status",
                json={"workspace_id": "telegram-default", "status": "ready"},
            )
            assert ready.status_code == 200
            submitted = await client.post(f"/api/v1/crm/public/repairs/{token}/review", json={"rating": 5, "comment": "Отлично"})
            assert submitted.status_code == 201
            public_after = await client.get(f"/api/v1/crm/public/repairs/{token}")
            assert public_after.json()["can_review"] is False
            assert public_after.json()["review"]["rating"] == 5
            assert (await client.get("/api/v1/crm/public/reviews?workspace_id=telegram-default")).json()["items"] == []
        async with factory() as session:
            review = await session.scalar(select(RepairReview))
            review.approved = True
            await session.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert len((await client.get("/api/v1/crm/public/reviews?workspace_id=telegram-default")).json()["items"]) == 1
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
