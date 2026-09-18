from __future__ import annotations

import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.agents.core import MatinAICore
from app.core.config import settings
from app.crm.service import get_repair_history
from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.telegram.customer_service import create_customer_repair, list_customer_repairs

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
STATUS_RU = {
    "new": "Новый заказ",
    "diagnostics": "Диагностика",
    "waiting_part": "Ожидание детали",
    "repairing": "Ремонт",
    "ready": "Готов",
    "issued": "Выдан",
    "cancelled": "Отменён",
}


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


def _display_name(message: Message) -> str | None:
    user = message.from_user
    if user is None:
        return None
    return " ".join(part for part in (user.first_name, user.last_name) if part) or user.username


def _telegram_user_id(message: Message) -> str:
    if message.from_user is None:
        raise RuntimeError("Telegram user is missing")
    return str(message.from_user.id)


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "MATINFIX\n"
        "Напишите модель устройства и что нужно сделать.\n"
        "Например: Realme C25s заменить дисплей\n\n"
        "/order — создать заказ в сервисе\n"
        "/myorders — мои заказы"
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды MATINFIX:\n"
        "/order Бренд Модель неисправность — создать заказ\n"
        "/myorders — показать мои заказы\n"
        "/start — начать заново\n\n"
        "Для предварительной цены просто напишите бренд, модель и неисправность."
    )


@router.message(Command("order"))
async def create_order(message: Message) -> None:
    text = (message.text or "").split(maxsplit=1)
    if len(text) != 2:
        await message.answer("Использование: /order Realme C25s заменить дисплей")
        return
    request = _extract_request(text[1])
    if request is None:
        await message.answer("Укажите бренд, модель и неисправность. Например: /order Realme C25s заменить дисплей")
        return

    brand, model, service = request
    decision = await core.handle_customer_price(brand, model, service)
    if decision.needs_master:
        await message.answer(decision.response)
        return

    try:
        async with SessionLocal() as session:
            repair = await create_customer_repair(
                session,
                workspace_id=settings.telegram_workspace_id,
                telegram_user_id=_telegram_user_id(message),
                username=message.from_user.username if message.from_user else None,
                display_name=_display_name(message),
                brand=brand,
                model=model,
                problem=service,
            )
    except Exception:
        logger.exception("Failed to create Telegram repair order")
        await message.answer("Не удалось сохранить заказ. Попробуйте ещё раз позже.")
        return
    await message.answer(
        f"Заказ создан.\n"
        f"📱 {brand} {model}\n"
        f"🛠 {service}\n"
        f"🆔 {repair.id[:8]}\n"
        f"📌 {STATUS_RU.get(repair.status, repair.status)}"
    )


@router.message(Command("myorders"))
async def my_orders(message: Message) -> None:
    try:
        async with SessionLocal() as session:
            repairs = await list_customer_repairs(
                session,
                workspace_id=settings.telegram_workspace_id,
                telegram_user_id=_telegram_user_id(message),
            )
    except Exception:
        logger.exception("Failed to list Telegram repair orders")
        await message.answer("Не удалось загрузить заказы. Попробуйте ещё раз позже.")
        return
    if not repairs:
        await message.answer("Заказов пока нет.")
        return
    lines = ["Мои заказы:"]
    for repair in repairs:
        lines.append(
            f"🆔 {repair.id[:8]} · {repair.brand} {repair.model} · "
            f"{STATUS_RU.get(repair.status, repair.status)}"
        )
    await message.answer("\n".join(lines))


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
            "Например: Realme C25s заменить дисплей\n"
            "Для создания заказа: /order Realme C25s заменить дисплей"
        )
        return

    brand, model, service = request
    decision = await core.handle_customer_price(brand, model, service)
    await message.answer(decision.response)


async def run() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    bot = Bot(settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    logger.info("MATINFIX Telegram worker started")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
