from __future__ import annotations

import pytest

from app.pricing.engine import PriceEngine, ServiceKind, detect_service


@pytest.mark.asyncio
async def test_unknown_year_does_not_select_old_xiaomi_table() -> None:
    decision = await PriceEngine().decide("Xiaomi", "Redmi Note", "замена дисплея")
    assert decision.price_rub is None
    assert decision.needs_master is True


@pytest.mark.asyncio
async def test_old_xiaomi_uses_universal_table() -> None:
    decision = await PriceEngine().decide("Xiaomi", "Redmi 9", "замена дисплея", model_year=2021)
    assert decision.price_rub == 1500


def test_speaker_replacement_is_not_cleaning() -> None:
    assert detect_service("замена динамика") is ServiceKind.POWER_VOLUME_SPEAKER
    assert detect_service("почистить динамик") is ServiceKind.CLEANING


def test_charging_synonyms_are_detected() -> None:
    assert detect_service("замена шлейфа зарядки") is ServiceKind.CHARGING_FLEX
    assert detect_service("замена разъема зарядки") is ServiceKind.CHARGING_PORT
