from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, Workspace
from app.telegram.bot import _customer_menu, _master_menu, _status_keyboard
from app.telegram.customer_service import (
    create_customer_repair,
    get_customer_repair,
    get_or_create_customer,
    list_customer_repairs,
)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(Workspace(id="telegram-a", name="Telegram A"))
        await db.commit()
        yield db
    await engine.dispose()


@pytest.mark.asyncio
async def test_telegram_user_maps_to_same_customer(session) -> None:
    first = await get_or_create_customer(
        session,
        workspace_id="telegram-a",
        telegram_user_id="123",
        username="matin",
        display_name="Matin",
    )
    second = await get_or_create_customer(
        session,
        workspace_id="telegram-a",
        telegram_user_id="123",
        username="matin_new",
        display_name="Matin New",
    )

    assert first.id == second.id
    assert second.name == "Matin New"


@pytest.mark.asyncio
async def test_telegram_repairs_are_visible_only_to_owner(session) -> None:
    repair = await create_customer_repair(
        session,
        workspace_id="telegram-a",
        telegram_user_id="123",
        username="matin",
        display_name="Matin",
        brand="Realme",
        model="C25s",
        problem="заменить дисплей",
    )

    own = await list_customer_repairs(
        session, workspace_id="telegram-a", telegram_user_id="123"
    )
    other = await list_customer_repairs(
        session, workspace_id="telegram-a", telegram_user_id="999"
    )

    assert [item.id for item in own] == [repair.id]
    customer = await get_or_create_customer(
        session,
        workspace_id="telegram-a",
        telegram_user_id="123",
        username="matin",
        display_name="Matin",
    )
    assert repair.customer_id == customer.id
    assert other == []


@pytest.mark.asyncio
async def test_customer_can_find_own_repair_by_short_id_only(session) -> None:
    repair = await create_customer_repair(
        session,
        workspace_id="telegram-a",
        telegram_user_id="123",
        username="matin",
        display_name="Matin",
        brand="Apple",
        model="iPhone 15",
        problem="замена батареи",
    )

    own = await get_customer_repair(
        session,
        workspace_id="telegram-a",
        telegram_user_id="123",
        repair_reference=repair.id[:8],
    )
    other = await get_customer_repair(
        session,
        workspace_id="telegram-a",
        telegram_user_id="999",
        repair_reference=repair.id[:8],
    )

    assert own is not None and own.id == repair.id
    assert other is None


def test_master_status_keyboard_contains_all_operational_statuses() -> None:
    keyboard = _status_keyboard("repair-123")
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert "repair_assign:repair-123" in callbacks
    assert "repair_card:repair-123" in callbacks
    assert "repair_history:repair-123" in callbacks
    assert "repair_status:repair-123:diagnostics" in callbacks
    assert "repair_status:repair-123:waiting_part" in callbacks
    assert "repair_status:repair-123:repairing" in callbacks
    assert "repair_status:repair-123:ready" in callbacks
    assert "repair_status:repair-123:issued" in callbacks
    assert "repair_status:repair-123:cancelled" in callbacks


def test_customer_menu_contains_main_actions() -> None:
    labels = [button.text for row in _customer_menu().keyboard for button in row]

    assert labels == [
        "📝 Создать заказ",
        "📦 Мои заказы",
        "🔎 Статус заказа",
        "📜 История заказа",
        "ℹ️ Помощь",
    ]


def test_master_menu_contains_work_queue_actions() -> None:
    labels = [button.text for row in _master_menu().keyboard for button in row]

    assert labels == [
        "📋 Все заказы",
        "🆕 Новые",
        "🔧 В ремонте",
        "✅ Готовые",
        "👤 Мои заказы",
        "📊 Статистика",
        "⭐ Отзывы",
        "🕒 На модерации",
        "📦 Склад",
        "ℹ️ Помощь",
    ]
