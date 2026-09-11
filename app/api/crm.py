from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.crm.service import change_repair_status, create_repair
from app.db.session import get_session

router = APIRouter(prefix="/api/v1/crm", tags=["crm"])


class RepairCreateRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=36)
    customer_name: str | None = Field(default=None, max_length=160)
    customer_phone: str | None = Field(default=None, max_length=40)
    brand: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    problem: str = Field(min_length=1, max_length=4000)


class RepairStatusRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=36)
    status: str = Field(min_length=1, max_length=32)


def repair_response(repair) -> dict:
    return {
        "id": repair.id,
        "workspace_id": repair.workspace_id,
        "customer_id": repair.customer_id,
        "brand": repair.brand,
        "model": repair.model,
        "problem": repair.problem,
        "status": repair.status,
        "created_at": repair.created_at,
    }


@router.post("/repairs", status_code=201)
async def create_repair_order(
    request: RepairCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repair = await create_repair(session, **request.model_dump())
    return repair_response(repair)


@router.patch("/repairs/{repair_id}/status")
async def update_repair_status(
    repair_id: str,
    request: RepairStatusRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        repair = await change_repair_status(
            session, workspace_id=request.workspace_id,
            repair_id=repair_id, status=request.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if repair is None:
        raise HTTPException(status_code=404, detail="repair order not found")
    return repair_response(repair)
