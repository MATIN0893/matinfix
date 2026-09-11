import pytest

from app.agents.core import MatinAICore
from app.agents.registry import AgentName


@pytest.mark.asyncio
async def test_customer_price_uses_deterministic_engine() -> None:
    core = MatinAICore()
    result = await core.handle_customer_price(
        "Realme", "C25s", "замена дисплея"
    )

    assert result.agent is AgentName.CUSTOMER
    assert result.needs_master is False
    assert "1500 ₽" in result.response
    assert "📱Цена без учета деталей" in result.response


def test_nss_routes_to_admin() -> None:
    core = MatinAICore()
    assert core.route_role("NSS") is AgentName.ADMIN
    assert core.route_role("обычный клиент") is AgentName.CUSTOMER
