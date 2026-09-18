from __future__ import annotations

import logging
from contextlib import suppress

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.db.models import Repair

logger = logging.getLogger(__name__)

STATUS_BUTTONS = (
    ("Диагностика", "diagnostics"),
    ("Ожидание детали", "waiting_part"),
    ("В ремонте", "repairing"),
    ("Готов", "ready"),
    ("Выдан", "issued"),
    ("Отменён", "cancelled"),
)


def public_repair_url(repair: Repair) -> str:
    return f"{settings.public_web_url.rstrip('/')}/?order={repair.public_token}"


def new_repair_message(repair: Repair) -> str:
    return (
        "Новая заявка с сайта MATINFIX\n\n"
        f"Устройство: {repair.brand} {repair.model}\n"
        f"Проблема: {repair.problem}\n"
        f"ID: {repair.id[:8]}\n\n"
        "Откройте публичную ссылку, чтобы проверить статус заказа."
    )


def new_repair_keyboard(repair: Repair) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть статус", url=public_repair_url(repair))],
            [InlineKeyboardButton(text="Комментарий / фото", callback_data=f"repair_note:{repair.id}")],
            [InlineKeyboardButton(text=label, callback_data=f"repair_status:{repair.id}:{status}") for label, status in STATUS_BUTTONS[:2]],
            [InlineKeyboardButton(text=label, callback_data=f"repair_status:{repair.id}:{status}") for label, status in STATUS_BUTTONS[2:4]],
            [InlineKeyboardButton(text=label, callback_data=f"repair_status:{repair.id}:{status}") for label, status in STATUS_BUTTONS[4:]],
        ]
    )


async def notify_masters_about_new_repair(repair: Repair) -> None:
    if not settings.telegram_bot_token or not settings.master_telegram_ids:
        return
    bot = Bot(settings.telegram_bot_token)
    keyboard = new_repair_keyboard(repair)
    try:
        for telegram_user_id in settings.master_telegram_ids:
            with suppress(Exception):
                await bot.send_message(
                    chat_id=telegram_user_id,
                    text=new_repair_message(repair),
                    reply_markup=keyboard,
                )
    finally:
        await bot.session.close()
