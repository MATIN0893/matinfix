from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, Repair, TelegramCustomer, Workspace, new_id


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

    customer = Customer(
        id=new_id(), workspace_id=workspace_id, name=display_name,
    )
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
    from app.crm.service import create_repair

    customer = await get_or_create_customer(
        session,
        workspace_id=workspace_id,
        telegram_user_id=telegram_user_id,
        username=username,
        display_name=display_name,
    )
    return await create_repair(
        session,
        workspace_id=workspace_id,
        customer_name=customer.name,
        customer_phone=customer.phone,
        brand=brand,
        model=model,
        problem=problem,
    )


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
