from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class ServiceKind(StrEnum):
    DIAGNOSTICS = "diagnostics"
    DISPLAY = "display"
    BATTERY = "battery"
    PASSWORD = "password"
    HYDROGEL = "hydrogel"
    CLEANING = "cleaning"
    MIC_BOTTOM = "mic_bottom"
    POWER_VOLUME_SPEAKER = "power_volume_speaker"
    CHARGING_FLEX = "charging_flex"
    CHARGING_PORT = "charging_port"
    EARPIECE = "earpiece"
    SCREEN_REPAIR = "screen_repair"
    SMALL_SOLDERING = "small_soldering"
    OTHER = "other"


@dataclass(frozen=True)
class PriceDecision:
    brand: str
    model: str
    service: str
    price_rub: int | None
    source: str
    needs_master: bool = False
    reason: str | None = None


BRANDS = ("xiaomi", "poco", "samsung", "honor", "tecno", "vivo", "oppo", "realme", "iphone", "apple")


def normalize_brand(value: str) -> str:
    value = value.strip().lower()
    aliases = {"apple": "iphone", "айфон": "iphone", "самсунг": "samsung", "хонор": "honor", "сяоми": "xiaomi", "редми": "xiaomi"}
    return aliases.get(value, value)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def detect_service(text: str) -> ServiceKind:
    t = normalize_text(text)
    if any(x in t for x in ("диагност", "провер")):
        return ServiceKind.DIAGNOSTICS
    if any(x in t for x in ("экран", "дисплей", "стекл")):
        return ServiceKind.DISPLAY
    if any(x in t for x in ("аккумулятор", "батаре")):
        return ServiceKind.BATTERY
    if any(x in t for x in ("пароль", "аккаунт", "разблок")):
        return ServiceKind.PASSWORD
    if any(x in t for x in ("гидрогел", "пленк")):
        return ServiceKind.HYDROGEL
    # Replacement/repair intent must win over generic cleaning words.
    if any(x in t for x in ("шлейф заряд", "charging flex", "шлейф зарядки")):
        return ServiceKind.CHARGING_FLEX
    if any(x in t for x in ("разъем заряд", "разъём заряд", "порт заряд", "гнездо заряд")):
        return ServiceKind.CHARGING_PORT
    if any(x in t for x in ("нижн", "нижняя плата")) and any(x in t for x in ("плат", "шлейф", "микрофон")):
        return ServiceKind.MIC_BOTTOM
    if any(x in t for x in ("разговорн", "слухов", "earpiece")):
        return ServiceKind.EARPIECE
    if any(x in t for x in ("кнопк", "громк", "питани")):
        return ServiceKind.POWER_VOLUME_SPEAKER
    if any(x in t for x in ("динамик", "speaker")) and any(x in t for x in ("замен", "ремонт", "не работает", "не слышно")):
        return ServiceKind.POWER_VOLUME_SPEAKER
    if any(x in t for x in ("чистк", "гряз", "прочист")):
        return ServiceKind.CLEANING
    if any(x in t for x in ("микрофон",)):
        return ServiceKind.MIC_BOTTOM
    if any(x in t for x in ("пайк", "контакт", "провод")):
        return ServiceKind.SMALL_SOLDERING
    return ServiceKind.OTHER


class PriceProvider:
    async def find(self, brand: str, model: str, service: str) -> int | None:
        raise NotImplementedError


class EmptyPriceProvider(PriceProvider):
    async def find(self, brand: str, model: str, service: str) -> int | None:
        return None


class PriceEngine:
    """Deterministic customer-price engine. LLM output must never be trusted as a price."""

    def __init__(self, providers: Iterable[PriceProvider] = ()) -> None:
        self.providers = tuple(providers)

    async def decide(self, brand: str, model: str, service: str, *, model_year: int | None = None) -> PriceDecision:
        b = normalize_brand(brand)
        m = normalize_text(model)
        s = service if isinstance(service, ServiceKind) else detect_service(service)

        for provider in self.providers:
            price = await provider.find(b, m, str(s))
            if price is not None:
                return PriceDecision(b, model, str(s), int(price), "provider")

        if s == ServiceKind.SMALL_SOLDERING:
            return PriceDecision(b, model, str(s), 300, "universal")

        # Tecno/Vivo/Oppo/Realme use the universal table for every model year.
        if b in {"tecno", "vivo", "oppo", "realme"}:
            table = {
                ServiceKind.DIAGNOSTICS: 500, ServiceKind.DISPLAY: 1500, ServiceKind.BATTERY: 1100,
                ServiceKind.PASSWORD: 1500, ServiceKind.HYDROGEL: 600, ServiceKind.CLEANING: 600,
                ServiceKind.MIC_BOTTOM: 1300, ServiceKind.POWER_VOLUME_SPEAKER: 1000,
                ServiceKind.CHARGING_FLEX: 1000, ServiceKind.CHARGING_PORT: 1200, ServiceKind.EARPIECE: 1200,
            }
            if s in table:
                return PriceDecision(b, model, str(s), table[s], "universal")
            return PriceDecision(b, model, str(s), None, "master", True, "service not covered")

        # For Xiaomi/Poco/Samsung/Honor, an unknown year is deliberately NOT
        # treated as an old device. A caller must provide the year to select
        # the 2022+ fixed-price rules.
        if b in {"xiaomi", "poco", "samsung", "honor"} and model_year is not None and model_year < 2022:
            table = {
                ServiceKind.DIAGNOSTICS: 500, ServiceKind.DISPLAY: 1500, ServiceKind.BATTERY: 1100,
                ServiceKind.PASSWORD: 1500, ServiceKind.HYDROGEL: 600, ServiceKind.CLEANING: 600,
                ServiceKind.MIC_BOTTOM: 1300, ServiceKind.POWER_VOLUME_SPEAKER: 1000,
                ServiceKind.CHARGING_FLEX: 1000, ServiceKind.CHARGING_PORT: 1200, ServiceKind.EARPIECE: 1200,
            }
            if s in table:
                return PriceDecision(b, model, str(s), table[s], "universal")
            return PriceDecision(b, model, str(s), None, "master", True, "motherboard or unsupported service")

        if b in {"xiaomi", "poco", "samsung", "honor"} and model_year is not None and model_year >= 2022:
            if s in {ServiceKind.DISPLAY, ServiceKind.MIC_BOTTOM, ServiceKind.BATTERY, ServiceKind.CHARGING_FLEX, ServiceKind.CHARGING_PORT, ServiceKind.EARPIECE}:
                return PriceDecision(b, model, str(s), 2000, "universal")

        return PriceDecision(b, model, str(s), None, "master", True, "not covered by deterministic catalog")
