from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientMessage:
    text: str
    language: str


LANGUAGE_NAMES = {
    "ru": "русском",
    "tg": "таджикском",
    "uz": "узбекском",
    "ky": "кыргызском",
    "en": "английском",
}


def detect_language(text: str) -> str:
    """Deterministic baseline language detection for customer messages."""
    t = text.lower()
    words = set(t.split())

    # Cyrillic-specific signals first. Shared words such as "телефон"
    # must not by themselves classify Tajik/Uzbek text.
    if any(c in t for c in "қҷҳӣӯ") or words.intersection(
        {"нарх", "нархи", "кор", "корро", "чанд", "лозим", "мешавад", "дорад", "иваз"}
    ):
        return "tg"
    if any(c in t for c in "ғўҳ") or words.intersection(
        {"narxi", "narx", "kerak", "qancha", "telefon", "almashtirish", "bo'ladi"}
    ):
        return "uz"
    if any(c in t for c in "ңөү") or words.intersection(
        {"канча", "керек", "алмаштыруу", "баасы", "телефонду"}
    ):
        return "ky"

    # Latin-only text is English only when it contains common English
    # function/content words; otherwise leave it as the Russian fallback.
    english_words = {
        "price", "screen", "display", "battery", "repair", "replace",
        "replacement", "phone", "how", "much", "cost", "charging",
    }
    if words.intersection(english_words):
        return "en"
    return "ru"


MASTER_TEXT = (
    "Контакты Мастера:\n"
    "Для детального разбора поломки, проверки схем аппарата и точного расчёта стоимости свяжитесь напрямую с мастером.\n"
    "👉 Telegram: @MATIN_0893 @Coichi\n"
    "Напишите модель устройства и что именно случилось"
)


MASTER_TEXT_BY_LANGUAGE = {
    "ru": MASTER_TEXT,
    "tg": (
        "Тамос бо Усто:\n"
        "Барои таҳлили муфассали нуқсон, санҷиши схема ва ҳисоб кардани нархи дақиқ мустақиман бо усто тамос гиред.\n"
        "👉 Telegram: @MATIN_0893 @Coichi\n"
        "Модели дастгоҳ ва мушкилотро нависед"
    ),
    "uz": (
        "Usta bilan aloqa:\n"
        "Nosozlikni batafsil tahlil qilish, sxemani tekshirish va aniq narxni hisoblash uchun usta bilan bevosita bog‘laning.\n"
        "👉 Telegram: @MATIN_0893 @Coichi\n"
        "Qurilma modeli va nima bo‘lganini yozing"
    ),
    "ky": (
        "Уста менен байланыш:\n"
        "Бузулууларды толук талдоо, схеманы текшерүү жана так бааны эсептөө үчүн уста менен түз байланышыңыз.\n"
        "👉 Telegram: @MATIN_0893 @Coichi\n"
        "Түзмөктүн моделин жана эмне болгонун жазыңыз"
    ),
    "en": (
        "Master contacts:\n"
        "For a detailed fault analysis, schematic check, and exact price calculation, contact the master directly.\n"
        "👉 Telegram: @MATIN_0893 @Coichi\n"
        "Write the device model and what happened"
    ),
}


def customer_price_text(brand: str, model: str, service: str, price: int | None) -> str:
    title = f"📱 {brand} {model}".strip()
    if price is None:
        return f"{title}\n🛠 Работа мастера: {service} — по договорённости\n📱Цена без учета деталей"
    return f"{title}\n🛠 Работа мастера: {service} — {price} ₽\n📱Цена без учета деталей"
