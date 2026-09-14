from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, Workspace
from app.telegram.customer_service import create_customer_repair, get_or_create_customer, list_customer_repairs


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
    assert other == []
