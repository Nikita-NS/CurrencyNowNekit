"""Валютные пары и периоды графиков.

Все пары записаны как «сколько quote за 1 base»: USD/RUB = рублей за 1 доллар.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PairDef:
    code: str          # RUB | USD | EUR | CNY
    pair: str          # "USD/RUB"
    title: str         # "Доллар США"
    unit: str          # "₽ за 1 $"
    symbol: str        # "₽"
    flag: str          # "🇺🇸"
    color: str
    yahoo: str         # тикер Yahoo Finance
    #: если прямого тикера нет — выводим из других пар: (a, операция, b)
    derive: tuple[str, str, str] | None = None


PAIRS: dict[str, PairDef] = {
    "RUB": PairDef(
        code="RUB",
        pair="RUB/USD",
        title="Рубль",
        unit="$ за 1 ₽",
        symbol="$",
        flag="🇷🇺",
        color="#3DDC97",
        yahoo="RUBUSD=X",
        derive=("USD/RUB", "invert", ""),
    ),
    "USD": PairDef(
        code="USD",
        pair="USD/RUB",
        title="Доллар США",
        unit="₽ за 1 $",
        symbol="₽",
        flag="🇺🇸",
        color="#5B9DFF",
        yahoo="USDRUB=X",
    ),
    "EUR": PairDef(
        code="EUR",
        pair="EUR/RUB",
        title="Евро",
        unit="₽ за 1 €",
        symbol="₽",
        flag="🇪🇺",
        color="#B18CFF",
        yahoo="EURRUB=X",
        derive=("EUR/USD", "*", "USD/RUB"),
    ),
    "CNY": PairDef(
        code="CNY",
        pair="CNY/RUB",
        title="Юань",
        unit="₽ за 1 ¥",
        symbol="₽",
        flag="🇨🇳",
        color="#FFB547",
        yahoo="CNYRUB=X",
        derive=("USD/RUB", "/", "USD/CNY"),
    ),
}

#: Порядок кнопок в меню (2x2): рубль, доллар / евро, юань.
PAIR_ORDER: tuple[str, ...] = ("RUB", "USD", "EUR", "CNY")

#: Пары, нужные для пересчёта кросс-курсов, но не показываемые кнопкой.
AUX_PAIRS: dict[str, str] = {
    "USD/RUB": "USDRUB=X",
    "RUB/USD": "RUBUSD=X",
    "EUR/USD": "EURUSD=X",
    "USD/CNY": "USDCNY=X",
    "USD/JPY": "USDJPY=X",
}


@dataclass(frozen=True)
class PeriodDef:
    code: str
    seconds: int
    title: str          # "за час"
    button: str         # "1 час"
    tick_seconds: int   # шаг подписей по X
    yahoo_interval: str
    yahoo_range: str
    from_daily: bool    # брать из daily_stats, а не из тиков


PERIODS: dict[str, PeriodDef] = {
    "1h": PeriodDef("1h", 3600, "за час", "1 час", 900, "5m", "1d", False),
    "24h": PeriodDef("24h", 86400, "за 24 часа", "24 часа", 4 * 3600, "15m", "2d", False),
    "7d": PeriodDef("7d", 7 * 86400, "за 7 дней", "7 дней", 86400, "1d", "1mo", True),
    "30d": PeriodDef("30d", 30 * 86400, "за 30 дней", "30 дней", 7 * 86400, "1d", "3mo", True),
}

DEFAULT_PERIOD = "1h"


def get_pair(code: str) -> PairDef:
    try:
        return PAIRS[code]
    except KeyError as exc:
        raise KeyError(f"Неизвестная валюта: {code}") from exc


def get_period(code: str) -> PeriodDef:
    try:
        return PERIODS[code]
    except KeyError as exc:
        raise KeyError(f"Неизвестный период: {code}") from exc
