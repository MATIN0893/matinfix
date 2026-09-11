from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentName
from app.pricing.engine import PriceEngine
from app.services.language import customer_price_text, detect_language


@dataclass(frozen=True)
class CoreDecision:
    agent: AgentName
    language: str
    response: str
    needs_master: bool = False


class MatinAICore:
    """Deterministic orchestration layer for MATIN's future AI agents.

    The core decides which agent owns a message and delegates price decisions
    to the deterministic PriceEngine. An LLM can be added later without
    becoming an authority for prices or accounting data.
    """

    def __init__(self, price_engine: PriceEngine | None = None) -> None:
        self.price_engine = price_engine or PriceEngine()

    @staticmethod
    def _is_accountant_message(text: str) -> bool:
        normalized = text.strip()
        return normalized == "NSS" or normalized.startswith("NSS ")

    async def handle_customer_price(
        self,
        brand: str,
        model: str,
        service: str,
        *,
        model_year: int | None = None,
    ) -> CoreDecision:
        language = detect_language(service)
        decision = await self.price_engine.decide(
            brand, model, service, model_year=model_year
        )
        if decision.needs_master:
            response = (
                "Контакты Мастера:\n"
                "Для детального разбора поломки, проверки схем аппарата "
                "и точного расчёта стоимости свяжитесь напрямую с мастером.\n"
                "👉 Telegram: @MATIN_0893 @Coichi\n"
                "Напишите модель устройства и что именно случилось"
            )
        else:
            response = customer_price_text(brand, model, service, decision.price_rub)
        return CoreDecision(
            agent=AgentName.CUSTOMER,
            language=language,
            response=response,
            needs_master=decision.needs_master,
        )

    def route_role(self, text: str) -> AgentName:
        if self._is_accountant_message(text):
            return AgentName.ADMIN
        return AgentName.CUSTOMER
