import asyncio

from app.pricing.engine import PriceEngine
from app.pricing.google_sheets import GoogleSheetsPriceProvider

URL = "https://docs.google.com/spreadsheets/d/1STYgA0ebn8DixCSVRR6bOog_nJ2A3Taq/export?format=csv"


async def main() -> None:
    provider = GoogleSheetsPriceProvider(URL)
    engine = PriceEngine(providers=(provider,))
    decision = await engine.decide("Realme", "Realme C11", "замена дисплея")
    assert decision.price_rub == 1500, decision
    assert decision.source == "google_sheets", decision
    print(f"PASS: {decision.brand} {decision.model} {decision.service} = {decision.price_rub} RUB ({decision.source})")
    print(f"PASS: loaded {len(provider._rows)} sheet rows")


if __name__ == "__main__":
    asyncio.run(main())
