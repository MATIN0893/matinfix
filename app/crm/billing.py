from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.crm.service import get_repair


async def set_repair_price(
    session: AsyncSession,
    *,
    workspace_id: str,
    repair_id: str,
    final_price: int,
    quoted_price: int | None = None,
):
    if final_price < 0 or (quoted_price is not None and quoted_price < 0):
        raise ValueError("price must be non-negative")
    repair = await get_repair(session, workspace_id=workspace_id, repair_id=repair_id)
    if repair is None:
        return None
    repair.final_price = final_price
    if quoted_price is not None:
        repair.quoted_price = quoted_price
    await session.commit()
    await session.refresh(repair)
    return repair


async def mark_repair_paid(
    session: AsyncSession, *, workspace_id: str, repair_id: str
):
    repair = await get_repair(session, workspace_id=workspace_id, repair_id=repair_id)
    if repair is None:
        return None
    if repair.final_price is None:
        raise ValueError("set final price before marking repair paid")
    repair.payment_status = "paid"
    repair.paid_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(repair)
    return repair
