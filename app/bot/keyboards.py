"""Клавиатуры: 4 валюты, периоды, сравнение."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..pairs import DEFAULT_PERIOD, PAIR_ORDER, PAIRS, PERIODS


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu() -> InlineKeyboardMarkup:
    pairs = [PAIRS[code] for code in PAIR_ORDER]
    rows = [
        [
            _btn(f"{pairs[0].flag} {pairs[0].title}", f"c:{pairs[0].code}:{DEFAULT_PERIOD}"),
            _btn(f"{pairs[1].flag} {pairs[1].title}", f"c:{pairs[1].code}:{DEFAULT_PERIOD}"),
        ],
        [
            _btn(f"{pairs[2].flag} {pairs[2].title}", f"c:{pairs[2].code}:{DEFAULT_PERIOD}"),
            _btn(f"{pairs[3].flag} {pairs[3].title}", f"c:{pairs[3].code}:{DEFAULT_PERIOD}"),
        ],
        [_btn("📊 Сравнить валюты", "cmp")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _period_row(current: str, callback) -> list[InlineKeyboardButton]:
    row = []
    for code, period in PERIODS.items():
        mark = "✓ " if code == current else ""
        row.append(_btn(f"{mark}{period.button}", callback(code)))
    return row


def chart_menu(code: str, period: str) -> InlineKeyboardMarkup:
    rows = [
        _period_row(period, lambda p: f"c:{code}:{p}"),
        [
            _btn("📊 Сравнить", f"cmp:{code}"),
            _btn("🖼 Без сжатия", f"hd:{code}:{period}"),
        ],
        [_btn("📐 SVG-файл", f"svg:{code}:{period}"), _btn("🏠 В меню", "menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def compare_picker(first: str | None) -> InlineKeyboardMarkup:
    """Выбор первой и второй валюты для сравнения."""
    if first is None:
        rows = []
        codes = list(PAIR_ORDER)
        for index in range(0, 4, 2):
            rows.append(
                [
                    _btn(f"{PAIRS[codes[index]].flag} {PAIRS[codes[index]].title}", f"cmp:{codes[index]}"),
                    _btn(f"{PAIRS[codes[index + 1]].flag} {PAIRS[codes[index + 1]].title}", f"cmp:{codes[index + 1]}"),
                ]
            )
        rows.append([_btn("🏠 В меню", "menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    rows = []
    others = [code for code in PAIR_ORDER if code != first]
    for index in range(0, len(others), 2):
        chunk = others[index:index + 2]
        rows.append([
            _btn(f"{PAIRS[code].flag} {PAIRS[code].pair}", f"cmp2:{first}:{code}:{DEFAULT_PERIOD}")
            for code in chunk
        ])
    rows.append([_btn("↩️ Другая пара", "cmp"), _btn("🏠 В меню", "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def compare_chart(a: str, b: str, period: str) -> InlineKeyboardMarkup:
    rows = [
        _period_row(period, lambda p: f"cmp2:{a}:{b}:{p}"),
        [
            _btn("🔁 Поменять валюты", f"cmp2:{b}:{a}:{period}"),
            _btn("🖼 Без сжатия", f"hdc:{a}:{b}:{period}"),
        ],
        [_btn("📐 SVG-файл", f"svgc:{a}:{b}:{period}"), _btn("🏠 В меню", "menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
