from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, Master, Repair, RepairAssignment, RepairStatusHistory, new_id

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
        from_status=None, to_status="new", changed_at=datetime.now(timezone.utc),
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
    session: AsyncSession,
    *,
    workspace_id: str,
    repair_id: str,
    status: str,
    comment: str | None = None,
    photo_file_id: str | None = None,
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
            comment=comment.strip() if comment else None,
            photo_file_id=photo_file_id,
            changed_at=datetime.now(timezone.utc),
        ))
    await session.commit()
    await session.refresh(repair)
    return repair


async def assign_repair_to_master(
    session: AsyncSession,
    *,
    workspace_id: str,
    repair_id: str,
    telegram_user_id: str,
    display_name: str,
) -> RepairAssignment | None:
    repair = await get_repair(session, workspace_id=workspace_id, repair_id=repair_id)
    if repair is None:
        return None
    master = await session.scalar(
        select(Master).where(
            Master.workspace_id == workspace_id,
            Master.telegram_user_id == telegram_user_id,
        )
    )
    if master is None:
        master = Master(
            id=new_id(),
            workspace_id=workspace_id,
            telegram_user_id=telegram_user_id,
            display_name=display_name,
        )
        session.add(master)
        await session.flush()
    assignment = await session.get(RepairAssignment, repair_id)
    if assignment is None:
        assignment = RepairAssignment(
            repair_id=repair_id,
            workspace_id=workspace_id,
            master_id=master.id,
        )
        session.add(assignment)
    else:
        assignment.master_id = master.id
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def get_repair_assignment(
    session: AsyncSession, *, workspace_id: str, repair_id: str
) -> tuple[RepairAssignment, Master] | None:
    result = await session.execute(
        select(RepairAssignment, Master)
        .join(Master, Master.id == RepairAssignment.master_id)
        .where(
            RepairAssignment.workspace_id == workspace_id,
            RepairAssignment.repair_id == repair_id,
        )
    )
    return result.one_or_none()
