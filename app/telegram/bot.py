from __future__ import annotations

import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import select

from app.agents.core import MatinAICore
from app.core.config import settings
from app.crm.service import (
    VALID_STATUSES,
    assign_repair_to_master,
    change_repair_status,
    get_repair_assignment,
    get_repair_history,
)
from app.crm.reviews import list_reviews, review_stats, set_review_approval
from app.db.models import Base, Repair, RepairAssignment
from app.db.session import SessionLocal, engine
from app.notifications import (
    notify_customer_review_published,
    notify_customer_status_changed,
    review_message,
    review_moderation_keyboard,
)
from app.telegram.customer_service import (
    create_customer_repair,
    get_customer_repair,
    get_repair_telegram_user_id,
    list_customer_repairs,
)

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


def _is_master(message: Message) -> bool:
    return _telegram_user_id(message) in settings.master_telegram_ids


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


def _status_keyboard(repair_id: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Взять заказ", callback_data=f"repair_assign:{repair_id}"),
         InlineKeyboardButton(text="Карточка", callback_data=f"repair_card:{repair_id}"),
         InlineKeyboardButton(text="История", callback_data=f"repair_history:{repair_id}")],
        [InlineKeyboardButton(text="Комментарий / фото", callback_data=f"repair_note:{repair_id}")],
        [InlineKeyboardButton(text="Диагностика", callback_data=f"repair_status:{repair_id}:diagnostics")],
        [InlineKeyboardButton(text="Ожидание детали", callback_data=f"repair_status:{repair_id}:waiting_part")],
        [InlineKeyboardButton(text="Ремонт", callback_data=f"repair_status:{repair_id}:repairing")],
        [InlineKeyboardButton(text="Готов", callback_data=f"repair_status:{repair_id}:ready")],
        [InlineKeyboardButton(text="Выдан", callback_data=f"repair_status:{repair_id}:issued"),
         InlineKeyboardButton(text="Отменён", callback_data=f"repair_status:{repair_id}:cancelled")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _customer_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Создать заказ"), KeyboardButton(text="📦 Мои заказы")],
            [KeyboardButton(text="🔎 Статус заказа"), KeyboardButton(text="📜 История заказа")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def _master_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Все заказы"), KeyboardButton(text="🆕 Новые")],
            [KeyboardButton(text="🔧 В ремонте"), KeyboardButton(text="✅ Готовые")],
            [KeyboardButton(text="👤 Мои заказы"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⭐ Отзывы")],
            [KeyboardButton(text="🕒 На модерации")],
            [KeyboardButton(text="📦 Склад")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    menu = _master_menu() if _is_master(message) else _customer_menu()
    await message.answer(
        "MATINFIX\n"
        "Напишите модель устройства и что нужно сделать.\n"
        "Например: Realme C25s заменить дисплей\n\n"
        "/order — создать заказ в сервисе\n"
        "/myorders — мои заказы",
        reply_markup=menu,
    )


@router.message(F.text == "📝 Создать заказ")
async def menu_create_order(message: Message) -> None:
    await message.answer("Напишите заказ так: /order Realme C25s заменить дисплей")


@router.message(F.text == "🔎 Статус заказа")
async def menu_status(message: Message) -> None:
    await message.answer("Введите: /status ID\nID можно взять из раздела «Мои заказы».")


@router.message(F.text == "📜 История заказа")
async def menu_history(message: Message) -> None:
    await message.answer("Введите: /history ID\nID можно взять из раздела «Мои заказы».")


@router.message(F.text == "ℹ️ Помощь")
async def menu_help(message: Message) -> None:
    await help_command(message)


@router.message(F.text == "📋 Все заказы")
async def menu_all_orders(message: Message) -> None:
    await _show_master_orders(message)


@router.message(F.text == "🆕 Новые")
async def menu_new_orders(message: Message) -> None:
    await _show_master_orders(message, "new")


@router.message(F.text == "🔧 В ремонте")
async def menu_repairing_orders(message: Message) -> None:
    await _show_master_orders(message, "repairing")


@router.message(F.text == "✅ Готовые")
async def menu_ready_orders(message: Message) -> None:
    await _show_master_orders(message, "ready")


@router.message(F.text == "👤 Мои заказы")
async def menu_my_master_orders(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    from app.db.models import Master
    async with SessionLocal() as session:
        master = await session.scalar(select(Master).where(
            Master.workspace_id == settings.telegram_workspace_id,
            Master.telegram_user_id == _telegram_user_id(message),
        ))
        repairs = [] if master is None else list((await session.scalars(
            select(Repair)
            .join(RepairAssignment, RepairAssignment.repair_id == Repair.id)
            .where(
                Repair.workspace_id == settings.telegram_workspace_id,
                RepairAssignment.workspace_id == settings.telegram_workspace_id,
                RepairAssignment.master_id == master.id,
            ).limit(20)
        )).all())
    if not repairs:
        await message.answer("На вас пока нет назначенных заказов.")
        return
    await message.answer("Мои назначенные заказы:\n" + "\n".join(
        f"{repair.id[:8]} · {repair.brand} {repair.model} · {STATUS_RU.get(repair.status, repair.status)}"
        for repair in repairs
    ))


@router.message(F.text == "📊 Статистика")
async def menu_master_stats(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    from app.crm.analytics import daily_repair_stats
    async with SessionLocal() as session:
        stats = await daily_repair_stats(session, workspace_id=settings.telegram_workspace_id)
    await message.answer(
        "Статистика за сегодня (UTC):\n"
        f"Новых заказов: {stats['created_today']}\n"
        f"Выдано ремонтов: {stats['issued_today']}\n"
        f"Активная очередь: {stats['active_queue']}\n"
        f"Среднее время ремонта: {stats['average_repair_hours']} ч.\n"
        f"Оплачено сегодня: {stats['paid_revenue_today']} ₽"
    )


@router.message(F.text == "⭐ Отзывы")
async def menu_master_reviews(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    async with SessionLocal() as session:
        count, average = await review_stats(session, workspace_id=settings.telegram_workspace_id)
        reviews = await list_reviews(session, workspace_id=settings.telegram_workspace_id, limit=8)
    if not reviews:
        await message.answer("Отзывов пока нет.")
        return
    lines = [f"Отзывы клиентов\nСредняя оценка: {average:.1f}/5 ({count})\n"]
    for review, repair in reviews:
        stars = "★" * review.rating + "☆" * (5 - review.rating)
        comment = f" — {review.comment}" if review.comment else ""
        lines.append(f"{stars} · {repair.brand} {repair.model}{comment}")
    await message.answer("\n".join(lines))


@router.message(F.text == "🕒 На модерации")
async def menu_pending_reviews(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    async with SessionLocal() as session:
        pending = await list_reviews(
            session,
            workspace_id=settings.telegram_workspace_id,
            limit=10,
            approved_only=False,
        )
        pending = [(review, repair) for review, repair in pending if not review.approved]
    if not pending:
        await message.answer("Отзывов на модерации нет.")
        return
    await message.answer(f"На модерации: {len(pending)}")
    for review, repair in pending:
        await message.answer(
            review_message(repair, review),
            reply_markup=review_moderation_keyboard(review),
        )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды MATINFIX:\n"
        "/order Бренд Модель неисправность — создать заказ\n"
        "/myorders — показать мои заказы\n"
        "/status ID — узнать статус заказа\n"
        "/history ID — история ремонта, комментарии и фото\n"
        "/start — начать заново\n\n"
        "Для предварительной цены просто напишите бренд, модель и неисправность."
    )
    if _is_master(message):
        await message.answer(
            "Мастерские команды:\n"
            "/orders [STATUS] — список заказов или фильтр по статусу\n"
            "/assign ID — взять заказ в работу\n"
            "/setstatus ID STATUS — изменить статус\n"
            "/stock — остатки деталей\n"
            "/restock SKU QTY — пополнить остаток\n"
            "/reservepart ID SKU [QTY] — зарезервировать деталь\n"
            "/usepart ID SKU [QTY] — списать установленную деталь\n"
            "/setprice ID PRICE — установить итоговую цену\n"
            "/paid ID — отметить оплату"
        )


@router.message(Command("stock"))
async def master_stock(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    from app.crm.inventory import list_inventory
    async with SessionLocal() as session:
        parts = await list_inventory(session, workspace_id=settings.telegram_workspace_id)
    if not parts:
        await message.answer("Склад пока пуст.")
        return
    lines = ["Остатки склада:"]
    for part in parts:
        available = part.quantity - part.reserved_quantity
        warning = " ⚠️ ниже минимума" if available <= part.reorder_level else ""
        lines.append(f"{part.sku} · {part.name}: {available} доступно, {part.reserved_quantity} резерв{warning}")
    await message.answer("\n".join(lines))


@router.message(F.text == "📦 Склад")
async def menu_master_stock(message: Message) -> None:
    await master_stock(message)


async def _handle_part_command(message: Message, *, action: str) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    parts = (message.text or "").split()
    if len(parts) not in {3, 4}:
        await message.answer(f"Использование: /{action} ID SKU [QTY]")
        return
    try:
        quantity = int(parts[3]) if len(parts) == 4 else 1
        async with SessionLocal() as session:
            from app.crm.inventory import reserve_part, use_part
            operation = reserve_part if action == "reservepart" else use_part
            part, usage = await operation(
                session, workspace_id=settings.telegram_workspace_id,
                repair_id=parts[1], sku=parts[2], quantity=quantity,
            )
    except (ValueError, TypeError) as exc:
        await message.answer(f"Операция со складом не выполнена: {exc}")
        return
    available = part.quantity - part.reserved_quantity
    verb = "зарезервировано" if action == "reservepart" else "списано"
    await message.answer(f"{parts[2]}: {quantity} шт. {verb}. Доступно: {available}.")


@router.message(Command("restock"))
async def master_restock(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Использование: /restock SKU QTY")
        return
    try:
        from app.crm.inventory import restock_part
        async with SessionLocal() as session:
            part = await restock_part(
                session,
                workspace_id=settings.telegram_workspace_id,
                sku=parts[1],
                quantity=int(parts[2]),
            )
    except (ValueError, TypeError) as exc:
        await message.answer(f"Пополнение не выполнено: {exc}")
        return
    await message.answer(
        f"{part.sku}: склад пополнен. Доступно: {part.quantity - part.reserved_quantity}."
    )


@router.message(Command("reservepart"))
async def master_reserve_part(message: Message) -> None:
    await _handle_part_command(message, action="reservepart")


@router.message(Command("usepart"))
async def master_use_part(message: Message) -> None:
    await _handle_part_command(message, action="usepart")


@router.message(Command("setprice"))
async def master_set_price(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Использование: /setprice ID PRICE")
        return
    try:
        from app.crm.billing import set_repair_price
        async with SessionLocal() as session:
            repair = await set_repair_price(
                session, workspace_id=settings.telegram_workspace_id,
                repair_id=parts[1], final_price=int(parts[2]),
            )
    except (ValueError, TypeError) as exc:
        await message.answer(f"Цена не установлена: {exc}")
        return
    if repair is None:
        await message.answer("Заказ не найден.")
        return
    await message.answer(f"Заказ {repair.id[:8]}: итоговая цена {repair.final_price} ₽.")


@router.message(Command("paid"))
async def master_mark_paid(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Использование: /paid ID")
        return
    try:
        from app.crm.billing import mark_repair_paid
        async with SessionLocal() as session:
            repair = await mark_repair_paid(
                session, workspace_id=settings.telegram_workspace_id, repair_id=parts[1]
            )
    except (ValueError, TypeError) as exc:
        await message.answer(f"Оплата не отмечена: {exc}")
        return
    if repair is None:
        await message.answer("Заказ не найден.")
        return
    await message.answer(f"Заказ {repair.id[:8]} отмечен как оплаченный: {repair.final_price} ₽.")


@router.message(Command("orders"))
async def master_orders(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    await _show_master_orders(message, parts[1].strip() if len(parts) == 2 else None)


async def _show_master_orders(message: Message, status_filter: str | None = None) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    if status_filter and status_filter not in VALID_STATUSES:
        await message.answer(
            "Неизвестный статус. Доступные статусы: "
            f"{', '.join(sorted(VALID_STATUSES))}"
        )
        return
    async with SessionLocal() as session:
        from app.crm.service import list_repairs
        repairs = await list_repairs(
            session,
            workspace_id=settings.telegram_workspace_id,
            status=status_filter,
            limit=20,
        )
        if not repairs:
            suffix = f" со статусом {status_filter}" if status_filter else ""
            await message.answer(f"Заказов{suffix} пока нет.")
            return
        title = f"Заказы: {status_filter}" if status_filter else "Все заказы"
        lines = [title + ":"]
        for repair in repairs:
            assignment = await get_repair_assignment(
                session, workspace_id=settings.telegram_workspace_id, repair_id=repair.id
            )
            master_text = f" · мастер: {assignment[1].display_name}" if assignment else " · не назначен"
            lines.append(
                f"{repair.id[:8]} · {repair.brand} {repair.model} · "
                f"{STATUS_RU.get(repair.status, repair.status)}{master_text}"
            )
            await message.answer(
                f"Заказ {repair.id[:8]}\n{repair.brand} {repair.model}\n"
                f"Статус: {STATUS_RU.get(repair.status, repair.status)}{master_text}",
                reply_markup=_status_keyboard(repair.id),
            )
    await message.answer("\n".join(lines))


async def _moderate_review(callback: CallbackQuery, approved: bool) -> None:
    if callback.from_user is None or str(callback.from_user.id) not in settings.master_telegram_ids:
        await callback.answer("Команда доступна только мастеру.", show_alert=True)
        return
    review_id = (callback.data or "").split(":", maxsplit=1)[1]
    repair = None
    customer_telegram_id = None
    async with SessionLocal() as session:
        review = await set_review_approval(session, review_id=review_id, approved=approved)
        if review is not None and approved:
            repair = await session.get(Repair, review.repair_id)
            if repair is not None:
                customer_telegram_id = await get_repair_telegram_user_id(
                    session, workspace_id=repair.workspace_id, repair_id=repair.id
                )
    if review is None:
        await callback.answer("Отзыв не найден.", show_alert=True)
        return
    await callback.answer("Отзыв опубликован." if approved else "Отзыв скрыт.")
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Отзыв опубликован на сайте." if approved else "Отзыв скрыт и не показывается на сайте.")
    if approved and repair is not None and customer_telegram_id and callback.bot:
        await notify_customer_review_published(repair, customer_telegram_id, bot=callback.bot)


@router.callback_query(lambda query: query.data and query.data.startswith("review_approve:"))
async def review_approve_callback(callback: CallbackQuery) -> None:
    await _moderate_review(callback, True)


@router.callback_query(lambda query: query.data and query.data.startswith("review_reject:"))
async def review_reject_callback(callback: CallbackQuery) -> None:
    await _moderate_review(callback, False)


@router.callback_query(lambda query: query.data and query.data.startswith("repair_status:"))
async def repair_status_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or str(callback.from_user.id) not in settings.master_telegram_ids:
        await callback.answer("Команда доступна только мастеру.", show_alert=True)
        return
    _, repair_id, status = (callback.data or "").split(":", maxsplit=2)
    if status not in VALID_STATUSES:
        await callback.answer("Неизвестный статус.", show_alert=True)
        return
    async with SessionLocal() as session:
        repair = await change_repair_status(
            session,
            workspace_id=settings.telegram_workspace_id,
            repair_id=repair_id,
            status=status,
        )
        if repair is None:
            await callback.answer("Заказ не найден.", show_alert=True)
            return
        customer_telegram_id = await get_repair_telegram_user_id(
            session, workspace_id=settings.telegram_workspace_id, repair_id=repair.id
        )
    await callback.answer(f"Статус: {STATUS_RU.get(status, status)}")
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=_status_keyboard(repair.id))
        await callback.message.answer(
            f"Заказ {repair.id[:8]} обновлён: {STATUS_RU.get(repair.status, repair.status)}"
        )
    if customer_telegram_id and callback.bot:
        await notify_customer_status_changed(repair, customer_telegram_id, bot=callback.bot)


@router.callback_query(lambda query: query.data and query.data.startswith("repair_assign:"))
async def repair_assign_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or str(callback.from_user.id) not in settings.master_telegram_ids:
        await callback.answer("Команда доступна только мастеру.", show_alert=True)
        return
    repair_id = (callback.data or "").split(":", maxsplit=1)[1]
    async with SessionLocal() as session:
        repair = await session.get(Repair, repair_id)
        if repair is None or repair.workspace_id != settings.telegram_workspace_id:
            await callback.answer("Заказ не найден.", show_alert=True)
            return
        assignment = await assign_repair_to_master(
            session,
            workspace_id=settings.telegram_workspace_id,
            repair_id=repair.id,
            telegram_user_id=str(callback.from_user.id),
            display_name=callback.from_user.full_name or "Мастер",
        )
    await callback.answer("Заказ назначен вам.")
    if callback.message is not None and assignment is not None:
        await callback.message.answer(f"Заказ {assignment.repair_id[:8]} назначен вам.")


@router.callback_query(lambda query: query.data and query.data.startswith("repair_note:"))
async def repair_note_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or str(callback.from_user.id) not in settings.master_telegram_ids:
        await callback.answer("Команда доступна только мастеру.", show_alert=True)
        return
    repair_id = (callback.data or "").split(":", maxsplit=1)[1]
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            f"Для заказа {repair_id[:8]} отправьте:\n"
            f"/note {repair_id[:8]} текст комментария\n\n"
            "Или отправьте фото с подписью:\n"
            f"/note {repair_id[:8]} что сделано на фото"
        )


@router.callback_query(lambda query: query.data and query.data.startswith("repair_card:"))
async def repair_card_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or str(callback.from_user.id) not in settings.master_telegram_ids:
        await callback.answer("Команда доступна только мастеру.", show_alert=True)
        return
    repair_id = (callback.data or "").split(":", maxsplit=1)[1]
    async with SessionLocal() as session:
        repair = await session.get(Repair, repair_id)
        if repair is None or repair.workspace_id != settings.telegram_workspace_id:
            await callback.answer("Заказ не найден.", show_alert=True)
            return
        assignment = await get_repair_assignment(
            session, workspace_id=settings.telegram_workspace_id, repair_id=repair.id
        )
    await callback.answer()
    master_text = assignment[1].display_name if assignment else "не назначен"
    if callback.message is not None:
        await callback.message.answer(
            f"Карточка заказа {repair.id[:8]}\n"
            f"📱 {repair.brand} {repair.model}\n"
            f"🛠 {repair.problem}\n"
            f"📌 {STATUS_RU.get(repair.status, repair.status)}\n"
            f"👤 Мастер: {master_text}"
        )


@router.callback_query(lambda query: query.data and query.data.startswith("repair_history:"))
async def repair_history_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or str(callback.from_user.id) not in settings.master_telegram_ids:
        await callback.answer("Команда доступна только мастеру.", show_alert=True)
        return
    repair_id = (callback.data or "").split(":", maxsplit=1)[1]
    async with SessionLocal() as session:
        repair = await session.get(Repair, repair_id)
        if repair is None or repair.workspace_id != settings.telegram_workspace_id:
            await callback.answer("Заказ не найден.", show_alert=True)
            return
        history = await get_repair_history(
            session, workspace_id=settings.telegram_workspace_id, repair_id=repair.id
        )
    await callback.answer()
    if callback.message is not None:
        lines = [f"История заказа {repair.id[:8]}:"]
        lines.extend(
            f"{item.from_status or '—'} → {item.to_status}"
            + (f" · {item.comment}" if item.comment else "")
            + (" · фото" if item.photo_file_id else "")
            for item in history
        )
        await callback.message.answer("\n".join(lines))


@router.message(Command("assign"))
async def master_assign(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Использование: /assign ID")
        return
    async with SessionLocal() as session:
        repairs = await session.scalars(
            select(Repair).where(
                Repair.workspace_id == settings.telegram_workspace_id,
                Repair.id.startswith(parts[1].strip().lower()),
            ).limit(2)
        )
        matches = list(repairs.all())
        if len(matches) != 1:
            await message.answer("Заказ не найден или ID неоднозначен.")
            return
        assignment = await assign_repair_to_master(
            session,
            workspace_id=settings.telegram_workspace_id,
            repair_id=matches[0].id,
            telegram_user_id=_telegram_user_id(message),
            display_name=_display_name(message) or "Мастер",
        )
    await message.answer(f"Заказ {assignment.repair_id[:8]} назначен вам.")


@router.message(Command("setstatus"))
async def master_set_status(message: Message) -> None:
    await _handle_master_status(message)


@router.message(Command("note"))
async def master_add_note(message: Message) -> None:
    await _handle_master_note(message)


@router.message(F.photo)
async def master_set_status_with_photo(message: Message) -> None:
    if (message.caption or "").strip().startswith("/setstatus"):
        await _handle_master_status(message)
    elif (message.caption or "").strip().startswith("/note"):
        await _handle_master_note(message)


async def _handle_master_status(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    command_text = message.text or message.caption or ""
    parts = command_text.split(maxsplit=3)
    if len(parts) < 3 or parts[2] not in VALID_STATUSES:
        await message.answer(
            "Использование: /setstatus ID STATUS [комментарий]\n"
            "Фото можно отправить с этой командой в подписи.\n"
            f"Статусы: {', '.join(sorted(VALID_STATUSES))}"
        )
        return
    comment = parts[3].strip() if len(parts) == 4 else None
    photo_file_id = message.photo[-1].file_id if message.photo else None
    async with SessionLocal() as session:
        repairs = await session.scalars(
            select(Repair).where(
                Repair.workspace_id == settings.telegram_workspace_id,
                Repair.id.startswith(parts[1].lower()),
            ).limit(2)
        )
        matches = list(repairs.all())
        if len(matches) != 1:
            await message.answer("Заказ не найден или ID неоднозначен.")
            return
        repair = await change_repair_status(
            session,
            workspace_id=settings.telegram_workspace_id,
            repair_id=matches[0].id,
            status=parts[2],
            comment=comment,
            photo_file_id=photo_file_id,
        )
        customer_telegram_id = await get_repair_telegram_user_id(
            session, workspace_id=settings.telegram_workspace_id, repair_id=repair.id
        )
    attachment = " с фото" if photo_file_id else ""
    note = f" Комментарий: {comment}" if comment else ""
    await message.answer(
        f"Заказ {repair.id[:8]}: {STATUS_RU.get(repair.status, repair.status)}{attachment}.{note}"
    )
    if customer_telegram_id:
        await notify_customer_status_changed(
            repair, customer_telegram_id, comment=comment, bot=message.bot
        )


async def _handle_master_note(message: Message) -> None:
    if not _is_master(message):
        await message.answer("Команда доступна только мастеру.")
        return
    command_text = message.text or message.caption or ""
    parts = command_text.split(maxsplit=2)
    photo_file_id = message.photo[-1].file_id if message.photo else None
    if len(parts) < 3 and not photo_file_id:
        await message.answer("Использование: /note ID комментарий. Для фото отправьте фото с этой подписью.")
        return
    comment = parts[2].strip() if len(parts) == 3 else None
    async with SessionLocal() as session:
        repairs = await session.scalars(
            select(Repair).where(
                Repair.workspace_id == settings.telegram_workspace_id,
                Repair.id.startswith(parts[1].lower()),
            ).limit(2)
        )
        matches = list(repairs.all())
        if len(matches) != 1:
            await message.answer("Заказ не найден или ID неоднозначен.")
            return
        repair = await change_repair_status(
            session,
            workspace_id=settings.telegram_workspace_id,
            repair_id=matches[0].id,
            status=matches[0].status,
            comment=comment,
            photo_file_id=photo_file_id,
        )
    suffix = " Фото сохранено." if photo_file_id else ""
    await message.answer(f"Комментарий добавлен к заказу {repair.id[:8]}.{suffix}")


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
@router.message(F.text == "📦 Мои заказы")
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


@router.message(Command("status"))
async def order_status(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        await message.answer("Использование: /status ID\nID можно взять из /myorders.")
        return
    try:
        async with SessionLocal() as session:
            repair = await get_customer_repair(
                session,
                workspace_id=settings.telegram_workspace_id,
                telegram_user_id=_telegram_user_id(message),
                repair_reference=parts[1],
            )
    except Exception:
        logger.exception("Failed to get Telegram repair status")
        await message.answer("Не удалось загрузить статус. Попробуйте ещё раз позже.")
        return
    if repair is None:
        await message.answer("Заказ не найден среди ваших заказов. Проверьте ID в /myorders.")
        return
    await message.answer(
        f"Заказ {repair.id[:8]}\n"
        f"📱 {repair.brand} {repair.model}\n"
        f"🛠 {repair.problem}\n"
        f"📌 {STATUS_RU.get(repair.status, repair.status)}"
    )


@router.message(Command("history"))
async def customer_history(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        await message.answer("Использование: /history ID\nID можно взять из /myorders.")
        return
    async with SessionLocal() as session:
        repair = await get_customer_repair(
            session,
            workspace_id=settings.telegram_workspace_id,
            telegram_user_id=_telegram_user_id(message),
            repair_reference=parts[1],
        )
        if repair is None:
            await message.answer("Заказ не найден среди ваших заказов.")
            return
        history = await get_repair_history(
            session, workspace_id=settings.telegram_workspace_id, repair_id=repair.id
        )
    if not history:
        await message.answer(f"История заказа {repair.id[:8]} пока пуста.")
        return
    lines = [f"История заказа {repair.id[:8]}:"]
    for item in history:
        line = f"{item.from_status or '—'} → {item.to_status}"
        if item.comment:
            line += f"\nКомментарий: {item.comment}"
        if item.photo_file_id:
            line += "\n📷 Прикреплено фото"
        lines.append(line)
    await message.answer("\n\n".join(lines))
    for item in history:
        if item.photo_file_id:
            await message.answer_photo(
                item.photo_file_id,
                caption=f"Фото к статусу {STATUS_RU.get(item.to_status, item.to_status)}",
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
