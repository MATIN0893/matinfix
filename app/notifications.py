from __future__ import annotations

import logging
from contextlib import suppress

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.db.models import Repair, RepairReview

logger = logging.getLogger(__name__)

STATUS_BUTTONS = (
    ("Диагностика", "diagnostics"),
    ("Ожидание детали", "waiting_part"),
    ("В ремонте", "repairing"),
    ("Готов", "ready"),
    ("Выдан", "issued"),
    ("Отменён", "cancelled"),
)
STATUS_RU = {
    "new": "Новый заказ",
    "diagnostics": "Диагностика",
    "waiting_part": "Ожидание детали",
    "repairing": "В ремонте",
    "ready": "Готов",
    "issued": "Выдан",
    "cancelled": "Отменён",
}


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


def customer_status_message(repair: Repair, comment: str | None = None) -> str:
    text = (
        f"Обновление заказа {repair.id[:8]}\n"
        f"📱 {repair.brand} {repair.model}\n"
        f"📌 {STATUS_RU.get(repair.status, repair.status)}"
    )
    if comment:
        text += f"\n💬 {comment}"
    return text


def customer_status_keyboard(repair: Repair) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Открыть статус", url=public_repair_url(repair))]]
    )


def review_message(repair: Repair, review: RepairReview) -> str:
    stars = "★" * review.rating + "☆" * (5 - review.rating)
    text = (
        "Новый отзыв клиента MATINFIX\n\n"
        f"Устройство: {repair.brand} {repair.model}\n"
        f"Заказ: {repair.id[:8]}\n"
        f"Оценка: {stars}"
    )
    if review.comment:
        text += f"\nКомментарий: {review.comment}"
    return text


def review_moderation_keyboard(review: RepairReview) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"review_approve:{review.id}"),
                InlineKeyboardButton(text="🗑 Скрыть", callback_data=f"review_reject:{review.id}"),
            ],
            [InlineKeyboardButton(text="Открыть заказ", callback_data=f"repair_card:{review.repair_id}")],
        ]
    )


async def notify_masters_about_review(repair: Repair, review: RepairReview) -> None:
    if not settings.telegram_bot_token or not settings.master_telegram_ids:
        return
    bot = Bot(settings.telegram_bot_token)
    try:
        for telegram_user_id in settings.master_telegram_ids:
            with suppress(Exception):
                await bot.send_message(
                    chat_id=telegram_user_id,
                    text=review_message(repair, review),
                    reply_markup=review_moderation_keyboard(review),
                )
    finally:
        await bot.session.close()


async def notify_customer_status_changed(
    repair: Repair,
    telegram_user_id: str,
    *,
    comment: str | None = None,
    bot: Bot | None = None,
) -> None:
    if not settings.telegram_bot_token or not telegram_user_id:
        return
    owned_bot = bot is None
    client = bot or Bot(settings.telegram_bot_token)
    try:
        await client.send_message(
            telegram_user_id,
            customer_status_message(repair, comment),
            reply_markup=customer_status_keyboard(repair),
        )
    except Exception:
        logger.exception("Failed to notify customer about repair status")
    finally:
        if owned_bot:
            await client.session.close()


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
