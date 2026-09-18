from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, Repair, RepairStatusHistory, TelegramCustomer, Workspace, new_id


async def ensure_workspace(session: AsyncSession, workspace_id: str) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        workspace = Workspace(id=workspace_id, name="MATINFIX Telegram")
        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)
    return workspace


async def get_or_create_customer(
    session: AsyncSession,
    *,
    workspace_id: str,
    telegram_user_id: str,
    username: str | None,
    display_name: str | None,
) -> Customer:
    await ensure_workspace(session, workspace_id)
    link = await session.scalar(
        select(TelegramCustomer).where(
            TelegramCustomer.workspace_id == workspace_id,
            TelegramCustomer.telegram_user_id == telegram_user_id,
        )
    )
    if link is not None:
        customer = await session.get(Customer, link.customer_id)
        if customer is not None:
            link.username = username
            link.display_name = display_name
            customer.name = display_name or customer.name
            await session.commit()
            return customer

    customer = Customer(id=new_id(), workspace_id=workspace_id, name=display_name)
    session.add(customer)
    await session.flush()
    session.add(TelegramCustomer(
        id=new_id(), workspace_id=workspace_id, customer_id=customer.id,
        telegram_user_id=telegram_user_id, username=username, display_name=display_name,
    ))
    await session.commit()
    await session.refresh(customer)
    return customer


async def create_customer_repair(
    session: AsyncSession,
    *,
    workspace_id: str,
    telegram_user_id: str,
    username: str | None,
    display_name: str | None,
    brand: str,
    model: str,
    problem: str,
) -> Repair:
    customer = await get_or_create_customer(
        session,
        workspace_id=workspace_id,
        telegram_user_id=telegram_user_id,
        username=username,
        display_name=display_name,
    )
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


async def list_customer_repairs(
    session: AsyncSession,
    *,
    workspace_id: str,
    telegram_user_id: str,
    limit: int = 10,
) -> list[Repair]:
    link = await session.scalar(
        select(TelegramCustomer).where(
            TelegramCustomer.workspace_id == workspace_id,
            TelegramCustomer.telegram_user_id == telegram_user_id,
        )
    )
    if link is None:
        return []
    result = await session.scalars(
        select(Repair)
        .where(Repair.workspace_id == workspace_id, Repair.customer_id == link.customer_id)
        .order_by(Repair.created_at.desc(), Repair.id.desc())
        .limit(limit)
    )
    return list(result.all())


async def get_customer_repair(
    session: AsyncSession,
    *,
    workspace_id: str,
    telegram_user_id: str,
    repair_reference: str,
) -> Repair | None:
    """Return a customer's repair by full id or the short id shown by the bot."""
    link = await session.scalar(
        select(TelegramCustomer).where(
            TelegramCustomer.workspace_id == workspace_id,
            TelegramCustomer.telegram_user_id == telegram_user_id,
        )
    )
    if link is None:
        return None
    reference = repair_reference.strip().lower()
    result = await session.scalars(
        select(Repair)
        .where(
            Repair.workspace_id == workspace_id,
            Repair.customer_id == link.customer_id,
            Repair.id.startswith(reference),
        )
        .limit(2)
    )
    repairs = list(result.all())
    return repairs[0] if len(repairs) == 1 else None


async def get_repair_telegram_user_id(
    session: AsyncSession, *, workspace_id: str, repair_id: str
) -> str | None:
    result = await session.scalar(
        select(TelegramCustomer.telegram_user_id)
        .join(Repair, Repair.customer_id == TelegramCustomer.customer_id)
        .where(
            Repair.workspace_id == workspace_id,
            Repair.id == repair_id,
            TelegramCustomer.workspace_id == workspace_id,
        )
    )
    return result
