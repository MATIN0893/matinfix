from __future__ import annotations

from fastapi import APIRouter

from app.agents import AGENT_NAMES

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/architecture")
async def architecture() -> dict[str, object]:
    return {
        "product": "MATIN",
        "platform": "MATINFIX",
        "interfaces": ["telegram_bot", "mini_app", "web_dashboard", "mobile_app", "api"],
        "ai_core": {
            "name": "MATIN AI CORE",
            "agents": list(AGENT_NAMES),
        },
        "services": ["price", "stock", "crm", "accounting", "knowledge"],
    }
