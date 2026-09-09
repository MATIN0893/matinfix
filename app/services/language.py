from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientMessage:
    text: str
    language: str


LANGUAGE_NAMES = {
    "ru": "русском", "tg": "таджикском", "uz": "узбекском", "ky": "кыргызском", "en": "английском"
}


def detect_language(text: str) -> str:
    """Small deterministic baseline; production can add a model classifier without changing API."""
    t = text.lower()
    if any(c in t for c in "қҷҳӣӯ") or any(w in t.split() for w in ("нарх", "телефон", "кор")):
        return "tg"
    if any(c in t for c in "ғўқҳ") or any(w in t.split() for w in ("narxi", "telefon", "kerak")):
        return "uz"
    if any(c in t for c in "ңөү"):
        return "ky"
    if all(ord(c) < 128 for c in t if c.isalpha()) and t:
        return "en"
    return "ru"


MASTER_TEXT = (
    "Контакты Мастера:\n"
    "Для детального разбора поломки, проверки схем аппарата и точного расчёта стоимости свяжитесь напрямую с мастером.\n"
    "👉 Telegram: @MATIN_0893 @Coichi\n"
    "Напишите модель устройства и что именно случилось"
)


def customer_price_text(brand: str, model: str, service: str, price: int | None) -> str:
    title = f"📱 {brand} {model}".strip()
    if price is None:
        return f"{title}\n🛠 Работа мастера: {service} — по договорённости\n📱Цена без учета деталей"
    return f"{title}\n🛠 Работа мастера: {service} — {price} ₽\n📱Цена без учета деталей"
