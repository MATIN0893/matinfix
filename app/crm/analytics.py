from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Repair, RepairStatusHistory


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def daily_repair_stats(
    session: AsyncSession, *, workspace_id: str, now: datetime | None = None
) -> dict[str, int | float]:
    current = _as_utc(now or datetime.now(timezone.utc))
    assert current is not None
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    repairs = list((await session.scalars(
        select(Repair).where(Repair.workspace_id == workspace_id)
    )).all())
    repair_ids = [repair.id for repair in repairs]
    histories = []
    if repair_ids:
        histories = list((await session.scalars(
            select(RepairStatusHistory)
            .where(
                RepairStatusHistory.workspace_id == workspace_id,
                RepairStatusHistory.repair_id.in_(repair_ids),
            )
            .order_by(RepairStatusHistory.changed_at, RepairStatusHistory.id)
        )).all())

    created_today = sum(
        (_as_utc(repair.created_at) or current) >= day_start for repair in repairs
    )
    issued_today = sum(
        item.to_status == "issued" and (_as_utc(item.changed_at) or current) >= day_start
        for item in histories
    )
    active_queue = sum(repair.status not in {"issued", "cancelled"} for repair in repairs)

    first_issued: dict[str, datetime] = {}
    for item in histories:
        changed_at = _as_utc(item.changed_at)
        if item.to_status == "issued" and changed_at is not None and item.repair_id not in first_issued:
            first_issued[item.repair_id] = changed_at
    durations = []
    for repair in repairs:
        completed_at = first_issued.get(repair.id)
        created_at = _as_utc(repair.created_at)
        if completed_at and created_at:
            durations.append(max(0, int((completed_at - created_at).total_seconds() / 3600)))

    return {
        "created_today": created_today,
        "issued_today": issued_today,
        "active_queue": active_queue,
        "average_repair_hours": round(sum(durations) / len(durations), 1) if durations else 0.0,
    }
