from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, Repair, RepairStatusHistory, new_id

VALID_STATUSES = {"new", "diagnostics", "waiting_part", "repairing", "ready", "issued", "cancelled"}


async def create_repair(
    session: AsyncSession,
    *,
    workspace_id: str,
    customer_name: str | None,
    customer_phone: str | None,
    brand: str,
    model: str,
    problem: str,
) -> Repair:
    customer = None
    if customer_phone:
        customer = await session.scalar(
            select(Customer).where(
                Customer.workspace_id == workspace_id,
                Customer.phone == customer_phone,
            )
        )
    if customer is None:
        customer = Customer(
            id=new_id(), workspace_id=workspace_id,
            name=customer_name, phone=customer_phone,
        )
        session.add(customer)
        await session.flush()

    repair = Repair(
        id=new_id(), workspace_id=workspace_id, customer_id=customer.id,
        brand=brand.strip(), model=model.strip(), problem=problem.strip(), status="new",
    )
    session.add(repair)
    session.add(RepairStatusHistory(
        id=new_id(), workspace_id=workspace_id, repair_id=repair.id,
        from_status=None, to_status="new",
    ))
    await session.commit()
    await session.refresh(repair)
    return repair


async def get_repair(
    session: AsyncSession, *, workspace_id: str, repair_id: str
) -> Repair | None:
    return await session.scalar(
        select(Repair).where(Repair.id == repair_id, Repair.workspace_id == workspace_id)
    )


async def list_repairs(
    session: AsyncSession,
    *,
    workspace_id: str,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Repair]:
    query = select(Repair).where(Repair.workspace_id == workspace_id)
    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(f"unknown repair status: {status}")
        query = query.where(Repair.status == status)
    query = query.order_by(desc(Repair.created_at), desc(Repair.id)).offset(offset).limit(limit)
    result = await session.scalars(query)
    return list(result.all())


async def get_repair_history(
    session: AsyncSession, *, workspace_id: str, repair_id: str
) -> list[RepairStatusHistory]:
    query = (
        select(RepairStatusHistory)
        .where(
            RepairStatusHistory.workspace_id == workspace_id,
            RepairStatusHistory.repair_id == repair_id,
        )
        .order_by(RepairStatusHistory.changed_at, RepairStatusHistory.id)
    )
    result = await session.scalars(query)
    return list(result.all())


async def change_repair_status(
    session: AsyncSession, *, workspace_id: str, repair_id: str, status: str
) -> Repair | None:
    if status not in VALID_STATUSES:
        raise ValueError(f"unknown repair status: {status}")
    repair = await get_repair(session, workspace_id=workspace_id, repair_id=repair_id)
    if repair is None:
        return None
    previous_status = repair.status
    if previous_status != status:
        repair.status = status
        session.add(RepairStatusHistory(
            id=new_id(), workspace_id=workspace_id, repair_id=repair.id,
            from_status=previous_status, to_status=status,
        ))
    await session.commit()
    await session.refresh(repair)
    return repair
