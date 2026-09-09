from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.pricing.engine import PriceEngine
from app.services.language import customer_price_text, detect_language

router = APIRouter(prefix="/api/v1")
engine = PriceEngine()


class PriceRequest(BaseModel):
    brand: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    service: str = Field(min_length=1, max_length=128)
    model_year: int | None = Field(default=None, ge=1990, le=2100)


class PriceResponse(BaseModel):
    brand: str
    model: str
    service: str
    price_rub: int | None
    source: str
    needs_master: bool
    customer_text: str


@router.post("/price", response_model=PriceResponse, tags=["price"])
async def price(request: PriceRequest) -> PriceResponse:
    decision = await engine.decide(
        request.brand,
        request.model,
        request.service,
        model_year=request.model_year,
    )
    return PriceResponse(
        brand=request.brand,
        model=request.model,
        service=request.service,
        price_rub=decision.price_rub,
        source=decision.source,
        needs_master=decision.needs_master,
        customer_text=customer_price_text(
            request.brand,
            request.model,
            request.service,
            decision.price_rub,
        ),
    )


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/language", tags=["language"])
def language(request: MessageRequest) -> dict[str, str]:
    return {"language": detect_language(request.text)}
