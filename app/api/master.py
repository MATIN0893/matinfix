from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.master import MasterAI

router = APIRouter(prefix="/api/v1/master", tags=["master-ai"])
master_ai = MasterAI()


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


@router.post("/orders", status_code=201)
async def master_create_order(request: MasterOrderRequest) -> dict:
    decision = await master_ai.create_order(**request.model_dump())
    return {
        "agent": decision.agent.value,
        "action": decision.action,
        "response": decision.response,
        "repair_id": decision.repair_id,
    }


@router.patch("/orders/status")
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
