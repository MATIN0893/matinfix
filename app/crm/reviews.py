from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Repair, RepairReview, new_id

FINAL_REVIEW_STATUSES = {"ready", "issued"}


async def get_review_by_repair(session: AsyncSession, *, repair_id: str) -> RepairReview | None:
    return await session.scalar(select(RepairReview).where(RepairReview.repair_id == repair_id))


async def create_review(
    session: AsyncSession,
    *,
    repair: Repair,
    rating: int,
    comment: str | None,
) -> RepairReview:
    if repair.status not in FINAL_REVIEW_STATUSES:
        raise ValueError("review is available only after repair is ready or issued")
    if not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")
    existing = await get_review_by_repair(session, repair_id=repair.id)
    if existing is not None:
        raise ValueError("review already exists")
    review = RepairReview(
        id=new_id(),
        repair_id=repair.id,
        workspace_id=repair.workspace_id,
        rating=rating,
        comment=comment.strip() if comment and comment.strip() else None,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review
