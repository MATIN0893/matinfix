import pytest

from app.agents.core import MatinAICore
from app.agents.registry import AgentName
from app.services.language import detect_language


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


def test_customer_language_detection() -> None:
    assert detect_language("нархи телефон чанд аст") == "tg"
    assert detect_language("telefon narxi qancha") == "uz"
    assert detect_language("what is the price for screen replacement") == "en"


@pytest.mark.asyncio
async def test_master_transfer_uses_customer_language() -> None:
    core = MatinAICore()
    result = await core.handle_customer_price(
        "iPhone", "17 Pro", "замена неизвестной детали"
    )
    assert result.needs_master is True
    assert "Master contacts" in result.response
