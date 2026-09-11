from __future__ import annotations

import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.agents.core import MatinAICore
from app.core.config import settings

logger = logging.getLogger(__name__)
router = Router()
core = MatinAICore()

BRANDS = (
    "Apple", "iPhone", "Samsung", "Xiaomi", "Poco", "Redmi", "Honor",
    "Huawei", "Realme", "Oppo", "Vivo", "Tecno", "Infinix", "OnePlus",
    "Nokia", "Lenovo", "Asus", "Google",
)
SERVICE_MARKERS = (
    "замен", "ремонт", "почист", "диспле", "экран", "стекл", "батар",
    "аккумулятор", "заряд", "разъем", "разъём", "шлейф", "динамик",
    "микрофон", "кнопк", "пароль", "аккаунт", "прошив", "пайк", "свар",
    "screen", "battery", "charging", "display", "repair", "replace",
)


def _extract_request(text: str) -> tuple[str, str, str] | None:
    """Extract brand/model/service from a simple free-form customer message."""
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return None
    brand_match = next(
        (brand for brand in BRANDS if re.search(rf"(?i)\b{re.escape(brand)}\b", normalized)),
        None,
    )
    if not brand_match:
        return None
    match = re.search(rf"(?i)\b{re.escape(brand_match)}\b\s+(.+)", normalized)
    if not match:
        return None
    tail = match.group(1).strip()
    marker_positions = [
        m.start() for marker in SERVICE_MARKERS
        for m in re.finditer(re.escape(marker), tail, re.IGNORECASE)
    ]
    if not marker_positions:
        return None
    service_start = min(marker_positions)
    model = tail[:service_start].strip(" ,:-")
    service = tail[service_start:].strip(" ,:-")
    if not model or not service:
        return None
    return brand_match, model, service


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "MATINFIX\n"
        "Напишите модель устройства и что нужно сделать.\n"
        "Например: Realme C25s заменить дисплей"
    )


@router.message()
async def customer_message(message: Message) -> None:
    text = message.text or ""
    if text.strip() == settings.accountant_codeword:
        decision = core.handle_admin(text)
        if decision.response:
            await message.answer(decision.response)
        return

    request = _extract_request(text)
    if request is None:
        await message.answer(
            "Напишите в формате: бренд, модель и что случилось.\n"
            "Например: Realme C25s заменить дисплей"
        )
        return

    brand, model, service = request
    decision = await core.handle_customer_price(brand, model, service)
    await message.answer(decision.response)


async def run() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    logger.info("MATINFIX Telegram worker started")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
