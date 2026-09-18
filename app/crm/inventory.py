from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InventoryPart, Repair, RepairPartUsage, new_id
from app.crm.service import change_repair_status


async def list_inventory(session: AsyncSession, *, workspace_id: str) -> list[InventoryPart]:
    result = await session.scalars(
        select(InventoryPart)
        .where(InventoryPart.workspace_id == workspace_id)
        .order_by(InventoryPart.name, InventoryPart.sku)
    )
    return list(result.all())


async def upsert_inventory_part(
    session: AsyncSession,
    *,
    workspace_id: str,
    sku: str,
    name: str,
    quantity: int,
    reorder_level: int = 0,
) -> InventoryPart:
    if quantity < 0 or reorder_level < 0:
        raise ValueError("quantity and reorder_level must be non-negative")
    part = await session.scalar(select(InventoryPart).where(
        InventoryPart.workspace_id == workspace_id,
        InventoryPart.sku == sku.strip(),
    ))
    if part is None:
        part = InventoryPart(
            id=new_id(), workspace_id=workspace_id, sku=sku.strip(), name=name.strip(),
            quantity=quantity, reorder_level=reorder_level,
        )
        session.add(part)
    else:
        part.name = name.strip()
        part.quantity = quantity
        part.reorder_level = reorder_level
    await session.commit()
    await session.refresh(part)
    return part


async def restock_part(
    session: AsyncSession,
    *,
    workspace_id: str,
    sku: str,
    quantity: int,
) -> InventoryPart:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    part = await session.scalar(select(InventoryPart).where(
        InventoryPart.workspace_id == workspace_id, InventoryPart.sku == sku.strip()
    ))
    if part is None:
        raise ValueError("inventory part not found")
    part.quantity += quantity
    await session.commit()
    await session.refresh(part)
    return part


async def reserve_part(
    session: AsyncSession,
    *,
    workspace_id: str,
    repair_id: str,
    sku: str,
    quantity: int = 1,
) -> tuple[InventoryPart, RepairPartUsage]:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    repair = await session.scalar(select(Repair).where(
        Repair.id == repair_id, Repair.workspace_id == workspace_id
    ))
    part = await session.scalar(select(InventoryPart).where(
        InventoryPart.workspace_id == workspace_id, InventoryPart.sku == sku.strip()
    ))
    if repair is None:
        raise ValueError("repair order not found")
    if part is None:
        raise ValueError("inventory part not found")
    available = part.quantity - part.reserved_quantity
    if available < quantity:
        if repair.status not in {"issued", "cancelled"}:
            await change_repair_status(
                session,
                workspace_id=workspace_id,
                repair_id=repair_id,
                status="waiting_part",
                comment=f"Нехватка детали {part.sku}: доступно {available}, нужно {quantity}",
            )
        raise ValueError(f"not enough stock: available {available}")
    usage = await session.scalar(select(RepairPartUsage).where(
        RepairPartUsage.repair_id == repair_id, RepairPartUsage.part_id == part.id
    ))
    if usage is None:
        usage = RepairPartUsage(
            id=new_id(), workspace_id=workspace_id, repair_id=repair_id,
            part_id=part.id, reserved_quantity=0, used_quantity=0,
        )
        session.add(usage)
    part.reserved_quantity += quantity
    usage.reserved_quantity += quantity
    await session.commit()
    await session.refresh(part)
    await session.refresh(usage)
    return part, usage


async def use_part(
    session: AsyncSession,
    *,
    workspace_id: str,
    repair_id: str,
    sku: str,
    quantity: int = 1,
) -> tuple[InventoryPart, RepairPartUsage]:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    part = await session.scalar(select(InventoryPart).where(
        InventoryPart.workspace_id == workspace_id, InventoryPart.sku == sku.strip()
    ))
    if part is None:
        raise ValueError("inventory part not found")
    usage = await session.scalar(select(RepairPartUsage).where(
        RepairPartUsage.workspace_id == workspace_id,
        RepairPartUsage.repair_id == repair_id,
        RepairPartUsage.part_id == part.id,
    ))
    if usage is None or usage.reserved_quantity < quantity:
        raise ValueError("part is not reserved for this repair")
    usage.reserved_quantity -= quantity
    usage.used_quantity += quantity
    part.reserved_quantity -= quantity
    part.quantity -= quantity
    await session.commit()
    await session.refresh(part)
    await session.refresh(usage)
    return part, usage
