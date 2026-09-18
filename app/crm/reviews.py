from __future__ import annotations

from sqlalchemy import func, select
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


async def list_reviews(
    session: AsyncSession, *, workspace_id: str, limit: int = 10, approved_only: bool | None = True
) -> list[tuple[RepairReview, Repair]]:
    conditions = [RepairReview.workspace_id == workspace_id]
    if approved_only is True:
        conditions.append(RepairReview.approved.is_(True))
    elif approved_only is False:
        conditions.append(RepairReview.approved.is_(False))
    result = await session.execute(
        select(RepairReview, Repair)
        .join(Repair, Repair.id == RepairReview.repair_id)
        .where(*conditions)
        .order_by(RepairReview.created_at.desc(), RepairReview.id.desc())
        .limit(limit)
    )
    return list(result.all())


async def review_stats(session: AsyncSession, *, workspace_id: str) -> tuple[int, float]:
    result = await session.execute(
        select(func.count(RepairReview.id), func.avg(RepairReview.rating)).where(
            RepairReview.workspace_id == workspace_id,
            RepairReview.approved.is_(True),
        )
    )
    count, average = result.one()
    return int(count or 0), float(average or 0)


async def set_review_approval(
    session: AsyncSession, *, review_id: str, approved: bool
) -> RepairReview | None:
    review = await session.get(RepairReview, review_id)
    if review is None:
        return None
    review.approved = approved
    await session.commit()
    await session.refresh(review)
    return review
