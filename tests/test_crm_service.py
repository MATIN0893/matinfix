from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.crm.service import change_repair_status, create_repair, get_repair, get_repair_history, list_repairs
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
