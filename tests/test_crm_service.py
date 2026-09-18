from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.crm.service import (
    assign_repair_to_master,
    change_repair_status,
    create_repair,
    get_repair,
    get_repair_assignment,
    get_repair_history,
    list_repairs,
)
from app.crm.analytics import daily_repair_stats
from app.crm.inventory import reserve_part, upsert_inventory_part, use_part
from app.crm.billing import mark_repair_paid, set_repair_price
from app.db.models import Base, Workspace


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add_all([Workspace(id="workspace-a", name="A"), Workspace(id="workspace-b", name="B")])
        await db.commit()
        yield db
    await engine.dispose()


@pytest.mark.asyncio
async def test_repair_isolated_by_workspace(session) -> None:
    repair = await create_repair(
        session,
        workspace_id="workspace-a",
        customer_name="Client",
        customer_phone="+100",
        brand="Realme",
        model="C25s",
        problem="display",
    )

    assert await get_repair(session, workspace_id="workspace-a", repair_id=repair.id) is not None
    assert await get_repair(session, workspace_id="workspace-b", repair_id=repair.id) is None
    assert await change_repair_status(
        session, workspace_id="workspace-b", repair_id=repair.id, status="ready"
    ) is None


@pytest.mark.asyncio
async def test_status_history_records_creation_and_transition(session) -> None:
    repair = await create_repair(
        session,
        workspace_id="workspace-a",
        customer_name=None,
        customer_phone=None,
        brand="Xiaomi",
        model="Redmi Note",
        problem="charging",
    )

    await change_repair_status(
        session, workspace_id="workspace-a", repair_id=repair.id, status="diagnostics"
    )
    await change_repair_status(
        session, workspace_id="workspace-a", repair_id=repair.id, status="repairing"
    )

    history = await get_repair_history(session, workspace_id="workspace-a", repair_id=repair.id)
    assert [(item.from_status, item.to_status) for item in history] == [
        (None, "new"),
        ("new", "diagnostics"),
        ("diagnostics", "repairing"),
    ]


@pytest.mark.asyncio
async def test_status_history_keeps_comment_and_photo_reference(session) -> None:
    repair = await create_repair(
        session,
        workspace_id="workspace-a",
        customer_name=None,
        customer_phone=None,
        brand="Samsung",
        model="A1",
        problem="screen",
    )

    await change_repair_status(
        session,
        workspace_id="workspace-a",
        repair_id=repair.id,
        status="diagnostics",
        comment="Есть следы влаги",
        photo_file_id="telegram-file-123",
    )

    history = await get_repair_history(session, workspace_id="workspace-a", repair_id=repair.id)
    assert history[-1].comment == "Есть следы влаги"
    assert history[-1].photo_file_id == "telegram-file-123"


@pytest.mark.asyncio
async def test_list_repairs_filters_by_status_and_workspace(session) -> None:
    first = await create_repair(
        session,
        workspace_id="workspace-a",
        customer_name=None,
        customer_phone=None,
        brand="Samsung",
        model="A1",
        problem="screen",
    )
    second = await create_repair(
        session,
        workspace_id="workspace-a",
        customer_name=None,
        customer_phone=None,
        brand="Samsung",
        model="A2",
        problem="battery",
    )
    await create_repair(
        session,
        workspace_id="workspace-b",
        customer_name=None,
        customer_phone=None,
        brand="Samsung",
        model="B1",
        problem="screen",
    )
    await change_repair_status(
        session, workspace_id="workspace-a", repair_id=second.id, status="ready"
    )

    ready = await list_repairs(session, workspace_id="workspace-a", status="ready")
    new = await list_repairs(session, workspace_id="workspace-a", status="new")

    assert [repair.id for repair in ready] == [second.id]
    assert [repair.id for repair in new] == [first.id]
    assert all(repair.workspace_id == "workspace-a" for repair in ready + new)


@pytest.mark.asyncio
async def test_repair_assignment_is_workspace_scoped_and_replaceable(session) -> None:
    repair = await create_repair(
        session,
        workspace_id="workspace-a",
        customer_name="Client",
        customer_phone=None,
        brand="Realme",
        model="C25s",
        problem="display",
    )

    first = await assign_repair_to_master(
        session,
        workspace_id="workspace-a",
        repair_id=repair.id,
        telegram_user_id="master-1",
        display_name="Master One",
    )
    assert first is not None
    assignment = await get_repair_assignment(
        session, workspace_id="workspace-a", repair_id=repair.id
    )
    assert assignment is not None
    assert assignment[1].display_name == "Master One"

    second = await assign_repair_to_master(
        session,
        workspace_id="workspace-a",
        repair_id=repair.id,
        telegram_user_id="master-2",
        display_name="Master Two",
    )
    assert second is not None
    replacement = await get_repair_assignment(
        session, workspace_id="workspace-a", repair_id=repair.id
    )
    assert replacement is not None
    assert replacement[1].display_name == "Master Two"
    assert await get_repair_assignment(
        session, workspace_id="workspace-b", repair_id=repair.id
    ) is None


@pytest.mark.asyncio
async def test_daily_repair_stats_counts_created_issued_and_active(session) -> None:
    issued = await create_repair(
        session, workspace_id="workspace-a", customer_name=None, customer_phone=None,
        brand="Apple", model="iPhone", problem="battery",
    )
    await create_repair(
        session, workspace_id="workspace-a", customer_name=None, customer_phone=None,
        brand="Samsung", model="A1", problem="screen",
    )
    await change_repair_status(
        session, workspace_id="workspace-a", repair_id=issued.id, status="issued"
    )

    stats = await daily_repair_stats(session, workspace_id="workspace-a")

    assert stats["created_today"] == 2
    assert stats["issued_today"] == 1
    assert stats["active_queue"] == 1
    assert "average_repair_hours" in stats


@pytest.mark.asyncio
async def test_inventory_reserves_and_consumes_part(session) -> None:
    repair = await create_repair(
        session, workspace_id="workspace-a", customer_name=None, customer_phone=None,
        brand="Xiaomi", model="Redmi", problem="screen",
    )
    part = await upsert_inventory_part(
        session, workspace_id="workspace-a", sku="LCD-REDMI", name="Redmi display",
        quantity=3, reorder_level=1,
    )

    reserved_part, usage = await reserve_part(
        session, workspace_id="workspace-a", repair_id=repair.id, sku="LCD-REDMI", quantity=2
    )
    assert reserved_part.quantity == 3
    assert reserved_part.reserved_quantity == 2
    assert usage.reserved_quantity == 2

    consumed_part, consumed_usage = await use_part(
        session, workspace_id="workspace-a", repair_id=repair.id, sku="LCD-REDMI", quantity=1
    )
    assert consumed_part.quantity == 2
    assert consumed_part.reserved_quantity == 1
    assert consumed_usage.used_quantity == 1


@pytest.mark.asyncio
async def test_inventory_rejects_reservation_above_available_stock(session) -> None:
    repair = await create_repair(
        session, workspace_id="workspace-a", customer_name=None, customer_phone=None,
        brand="Apple", model="iPhone", problem="battery",
    )
    await upsert_inventory_part(
        session, workspace_id="workspace-a", sku="BAT-IPH", name="iPhone battery", quantity=1
    )

    with pytest.raises(ValueError, match="not enough stock"):
        await reserve_part(
            session, workspace_id="workspace-a", repair_id=repair.id, sku="BAT-IPH", quantity=2
        )
    refreshed = await get_repair(session, workspace_id="workspace-a", repair_id=repair.id)
    assert refreshed is not None
    assert refreshed.status == "waiting_part"
    history = await get_repair_history(session, workspace_id="workspace-a", repair_id=repair.id)
    assert "Нехватка детали BAT-IPH" in (history[-1].comment or "")


@pytest.mark.asyncio
async def test_repair_price_payment_and_revenue_are_recorded(session) -> None:
    repair = await create_repair(
        session, workspace_id="workspace-a", customer_name=None, customer_phone=None,
        brand="Apple", model="iPhone", problem="display",
    )
    with pytest.raises(ValueError, match="set final price"):
        await mark_repair_paid(session, workspace_id="workspace-a", repair_id=repair.id)
    await set_repair_price(
        session, workspace_id="workspace-a", repair_id=repair.id, final_price=4500
    )
    paid = await mark_repair_paid(session, workspace_id="workspace-a", repair_id=repair.id)
    assert paid is not None
    assert paid.payment_status == "paid"
    assert paid.paid_at is not None
    stats = await daily_repair_stats(session, workspace_id="workspace-a")
    assert stats["paid_revenue_today"] == 4500
