from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, Repair, new_id

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
    await session.commit()
    await session.refresh(repair)
    return repair


async def change_repair_status(
    session: AsyncSession, *, workspace_id: str, repair_id: str, status: str
) -> Repair | None:
    if status not in VALID_STATUSES:
        raise ValueError(f"unknown repair status: {status}")
    repair = await session.scalar(
        select(Repair).where(Repair.id == repair_id, Repair.workspace_id == workspace_id)
    )
    if repair is None:
        return None
    repair.status = status
    await session.commit()
    await session.refresh(repair)
    return repair
