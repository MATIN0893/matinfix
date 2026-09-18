from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.crm.service import (
    change_repair_status,
    create_repair,
    get_repair,
    get_repair_by_public_token,
    get_repair_history,
    list_repairs,
)
from app.db.session import get_session
from app.notifications import notify_masters_about_new_repair

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
    comment: str | None = Field(default=None, max_length=4000)
    photo_file_id: str | None = Field(default=None, max_length=256)


def repair_response(repair) -> dict:
    return {
        "id": repair.id,
        "public_token": repair.public_token,
        "workspace_id": repair.workspace_id,
        "customer_id": repair.customer_id,
        "brand": repair.brand,
        "model": repair.model,
        "problem": repair.problem,
        "status": repair.status,
        "quoted_price": repair.quoted_price,
        "final_price": repair.final_price,
        "payment_status": repair.payment_status,
        "paid_at": repair.paid_at,
        "created_at": repair.created_at,
    }


def history_response(item) -> dict:
    return {
        "id": item.id,
        "repair_id": item.repair_id,
        "from_status": item.from_status,
        "to_status": item.to_status,
        "comment": item.comment,
        "photo_file_id": item.photo_file_id,
        "changed_at": item.changed_at,
    }


def public_repair_response(repair, history) -> dict:
    return {
        "id": repair.id,
        "brand": repair.brand,
        "model": repair.model,
        "status": repair.status,
        "quoted_price": repair.quoted_price,
        "final_price": repair.final_price,
        "payment_status": repair.payment_status,
        "created_at": repair.created_at,
        "history": [history_response(item) for item in history],
    }


@router.post("/repairs", status_code=201)
async def create_repair_order(
    request: RepairCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repair = await create_repair(session, **request.model_dump())
    await notify_masters_about_new_repair(repair)
    return repair_response(repair)


@router.get("/repairs/{repair_id}")
async def get_repair_order(
    repair_id: str,
    workspace_id: str = Query(min_length=1, max_length=36),
    session: AsyncSession = Depends(get_session),
) -> dict:
    repair = await get_repair(session, workspace_id=workspace_id, repair_id=repair_id)
    if repair is None:
        raise HTTPException(status_code=404, detail="repair order not found")
    return repair_response(repair)


@router.get("/repairs/{repair_id}/history")
async def get_repair_order_history(
    repair_id: str,
    workspace_id: str = Query(min_length=1, max_length=36),
    session: AsyncSession = Depends(get_session),
) -> dict:
    repair = await get_repair(session, workspace_id=workspace_id, repair_id=repair_id)
    if repair is None:
        raise HTTPException(status_code=404, detail="repair order not found")
    history = await get_repair_history(session, workspace_id=workspace_id, repair_id=repair_id)
    return {"items": [history_response(item) for item in history]}


@router.get("/public/repairs/{public_token}")
async def get_public_repair_order(
    public_token: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repair = await get_repair_by_public_token(session, public_token=public_token)
    if repair is None:
        raise HTTPException(status_code=404, detail="public repair link not found")
    history = await get_repair_history(
        session, workspace_id=repair.workspace_id, repair_id=repair.id
    )
    return public_repair_response(repair, history)


@router.get("/repairs")
async def list_repair_orders(
    workspace_id: str = Query(min_length=1, max_length=36),
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        repairs = await list_repairs(
            session, workspace_id=workspace_id, status=status, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": [repair_response(repair) for repair in repairs], "limit": limit, "offset": offset}


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
            comment=request.comment,
            photo_file_id=request.photo_file_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if repair is None:
        raise HTTPException(status_code=404, detail="repair order not found")
    return repair_response(repair)
