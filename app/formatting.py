"""Единое форматирование чисел для картинок и подписей."""

from __future__ import annotations

from .charts.model import fmt_num, fmt_pct

MINUS = "\u2212"


def price_decimals(value: float) -> int:
    value = abs(value)
    if value >= 1:
        return 2
    if value >= 0.1:
        return 3
    if value >= 1e-4:
        return 5
    return 6


def price_text(value: float, symbol: str = "") -> str:
    text = fmt_num(value, price_decimals(value))
    return f"{text} {symbol}".strip()


def signed_pct(value: float, decimals: int = 2) -> str:
    return fmt_pct(value, decimals)


def delta_kind(value: float, epsilon: float = 1e-9) -> str:
    if value > epsilon:
        return "up"
    if value < -epsilon:
        return "down"
    return "flat"


def arrow(value: float, epsilon: float = 1e-9) -> str:
    if value > epsilon:
        return "▲"
    if value < -epsilon:
        return "▼"
    return "•"


def change_text(value: float) -> str:
    """'▲ 0,42 %' — для плашки на графике."""
    return f"{arrow(value)} {fmt_num(abs(value), 2)} %"


def percent_change(first: float, last: float) -> float:
    if first == 0:
        return 0.0
    return (last / first - 1.0) * 100.0


def plural(count: int, one: str, few: str, many: str) -> str:
    """61 точка / 62 точки / 65 точек."""
    value = abs(int(count)) % 100
    if 11 <= value <= 14:
        return many
    value %= 10
    if value == 1:
        return one
    if 2 <= value <= 4:
        return few
    return many
