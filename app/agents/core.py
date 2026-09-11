from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentName
from app.accounting.mode import AccountantMode
from app.pricing.engine import PriceEngine
from app.services.language import customer_price_text, detect_language


@dataclass(frozen=True)
class CoreDecision:
    agent: AgentName
    language: str
    response: str
    needs_master: bool = False


class MatinAICore:
    """Deterministic orchestration layer for MATIN AI agents.

    LLMs may later interpret free-form intent, but prices and accounting
    boundaries remain deterministic and authoritative.
    """

    def __init__(self, price_engine: PriceEngine | None = None, accountant: AccountantMode | None = None) -> None:
        self.price_engine = price_engine or PriceEngine()
        self.accountant = accountant or AccountantMode()

    @staticmethod
    def _is_accountant_message(text: str) -> bool:
        return text.strip() == "NSS"

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
        return CoreDecision(AgentName.CUSTOMER, language, response, decision.needs_master)

    def route_role(self, text: str) -> AgentName:
        if self._is_accountant_message(text):
            return AgentName.ADMIN
        return AgentName.CUSTOMER

    def handle_admin(self, text: str) -> CoreDecision:
        if not self._is_accountant_message(text):
            return CoreDecision(AgentName.CUSTOMER, detect_language(text), "", False)
        return CoreDecision(AgentName.ADMIN, "ru", self.accountant.handle(text) or "", False)
