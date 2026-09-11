from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentName
from app.crm.service import change_repair_status, create_repair
from app.db.session import SessionLocal


@dataclass(frozen=True)
class MasterDecision:
    agent: AgentName
    action: str
    response: str
    repair_id: str | None = None


class MasterAI:
    """Operational assistant for a repair master.

    The first production-safe version accepts explicit commands from the API.
    It never invents prices and every database operation is scoped by workspace.
    """

    async def create_order(
        self,
        *,
        workspace_id: str,
        customer_name: str | None,
        customer_phone: str | None,
        brand: str,
        model: str,
        problem: str,
    ) -> MasterDecision:
        async with SessionLocal() as session:
            repair = await create_repair(
                session,
                workspace_id=workspace_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
                brand=brand,
                model=model,
                problem=problem,
            )
        return MasterDecision(
            AgentName.MASTER,
            "create_repair",
            f"Заказ создан: {repair.brand} {repair.model}\nID: {repair.id}\nСтатус: {repair.status}",
            repair.id,
        )

    async def set_status(
        self, *, workspace_id: str, repair_id: str, status: str
    ) -> MasterDecision:
        async with SessionLocal() as session:
            repair = await change_repair_status(
                session,
                workspace_id=workspace_id,
                repair_id=repair_id,
                status=status,
            )
        if repair is None:
            return MasterDecision(AgentName.MASTER, "set_status", "Заказ не найден")
        return MasterDecision(
            AgentName.MASTER,
            "set_status",
            f"Заказ {repair.id}: статус → {repair.status}",
            repair.id,
        )
