from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.master import MasterAI
from app.core.config import settings
from app.crm.inventory import list_inventory, reserve_part, restock_part, use_part
from app.crm.billing import mark_repair_paid, set_repair_price
from app.db.session import get_session

router = APIRouter(prefix="/api/v1/master", tags=["master-ai"])
master_ai = MasterAI()


def require_master_key(x_master_key: str | None = Header(default=None)) -> None:
    """Require a shared key whenever one is configured."""
    if settings.master_api_key and x_master_key != settings.master_api_key:
        raise HTTPException(status_code=401, detail="invalid master api key")


class MasterOrderRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=36)
    customer_name: str | None = Field(default=None, max_length=160)
    customer_phone: str | None = Field(default=None, max_length=40)
    brand: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    problem: str = Field(min_length=1, max_length=4000)


class MasterStatusRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=36)
    repair_id: str = Field(min_length=1, max_length=36)
    status: str = Field(min_length=1, max_length=32)


class InventoryRestockRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=36)
    sku: str = Field(min_length=1, max_length=80)
    quantity: int = Field(gt=0, le=100000)


class InventoryRepairRequest(InventoryRestockRequest):
    repair_id: str = Field(min_length=1, max_length=36)


class RepairPriceRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=36)
    repair_id: str = Field(min_length=1, max_length=36)
    final_price: int = Field(ge=0, le=100000000)
    quoted_price: int | None = Field(default=None, ge=0, le=100000000)


class RepairPaymentRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=36)
    repair_id: str = Field(min_length=1, max_length=36)


@router.post("/orders", status_code=201, dependencies=[Depends(require_master_key)])
async def master_create_order(request: MasterOrderRequest) -> dict:
    decision = await master_ai.create_order(**request.model_dump())
    return {
        "agent": decision.agent.value,
        "action": decision.action,
        "response": decision.response,
        "repair_id": decision.repair_id,
    }


@router.patch("/orders/status", dependencies=[Depends(require_master_key)])
async def master_set_status(request: MasterStatusRequest) -> dict:
    try:
        decision = await master_ai.set_status(
            workspace_id=request.workspace_id,
            repair_id=request.repair_id,
            status=request.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if decision.repair_id is None:
        raise HTTPException(status_code=404, detail=decision.response)
    return {
        "agent": decision.agent.value,
        "action": decision.action,
        "response": decision.response,
        "repair_id": decision.repair_id,
    }


@router.get("/stock", dependencies=[Depends(require_master_key)])
async def master_stock(workspace_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    parts = await list_inventory(session, workspace_id=workspace_id)
    return {"items": [
        {
            "sku": part.sku,
            "name": part.name,
            "quantity": part.quantity,
            "reserved_quantity": part.reserved_quantity,
            "available_quantity": part.quantity - part.reserved_quantity,
            "reorder_level": part.reorder_level,
        }
        for part in parts
    ]}


@router.post("/stock/restock", dependencies=[Depends(require_master_key)])
async def master_restock(
    request: InventoryRestockRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        part = await restock_part(session, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"sku": part.sku, "quantity": part.quantity, "reserved_quantity": part.reserved_quantity}


@router.post("/stock/reserve", dependencies=[Depends(require_master_key)])
async def master_reserve(
    request: InventoryRepairRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        part, usage = await reserve_part(session, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"sku": part.sku, "reserved_quantity": usage.reserved_quantity}


@router.post("/stock/use", dependencies=[Depends(require_master_key)])
async def master_use(
    request: InventoryRepairRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        part, usage = await use_part(session, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"sku": part.sku, "quantity": part.quantity, "used_quantity": usage.used_quantity}


@router.post("/billing/price", dependencies=[Depends(require_master_key)])
async def master_set_price(
    request: RepairPriceRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    repair = await set_repair_price(session, **request.model_dump())
    if repair is None:
        raise HTTPException(status_code=404, detail="repair order not found")
    return {"repair_id": repair.id, "final_price": repair.final_price, "payment_status": repair.payment_status}


@router.post("/billing/paid", dependencies=[Depends(require_master_key)])
async def master_mark_paid(
    request: RepairPaymentRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        repair = await mark_repair_paid(session, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if repair is None:
        raise HTTPException(status_code=404, detail="repair order not found")
    return {"repair_id": repair.id, "final_price": repair.final_price, "payment_status": repair.payment_status}
