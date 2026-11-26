"""Карточка-меню: 4 валюты плитками, картинка для сообщения с кнопками."""

from __future__ import annotations

from .model import DESIGN_W, Layout, Rect, Text
from .theme import SERIES_COLORS, THEME
from ..formatting import change_text, delta_kind, price_text
from ..pairs import PAIRS, PAIR_ORDER

CARD_W = DESIGN_W
CARD_H = 620

TILE_W = 552.0
TILE_H = 158.0
POSITIONS = {
    "RUB": (64.0, 168.0),
    "USD": (664.0, 168.0),
    "EUR": (64.0, 350.0),
    "CNY": (664.0, 350.0),
}


def build_menu(values: dict[str, tuple[float, float]] | None = None) -> Layout:
    """values: {код: (цена, изменение_в_%)} — можно не передавать."""
    theme = THEME
    layout = Layout(
        width=CARD_W,
        height=CARD_H,
        bg_top=theme.bg_top,
        bg_bottom=theme.bg_bottom,
        title="Курсы валют — меню",
    )
    values = values or {}

    layout.texts.append(Text(64.0, 96.0, "Курсы валют", 40, theme.text, "bold"))
    layout.texts.append(
        Text(64.0, 132.0, "График за час · сравнение валют · история по дням", 19, theme.text_muted)
    )

    for code in PAIR_ORDER:
        pair = PAIRS[code]
        color = SERIES_COLORS.get(code, pair.color)
        x0, y0 = POSITIONS[code]
        x1, y1 = x0 + TILE_W, y0 + TILE_H

        layout.rects.append(
            Rect(x0, y0, x1, y1, fill=theme.panel, radius=24.0, stroke=theme.border, stroke_width=1.0)
        )
        layout.rects.append(
            Rect(x0 + 26, y0 + 28, x0 + 88, y0 + 90, fill=color, alpha=0.16, radius=31.0)
        )
        layout.texts.append(Text(x0 + 57, y0 + 67, code, 15, color, "bold", "middle"))

        layout.texts.append(Text(x0 + 104, y0 + 54, pair.title, 22, theme.text, "bold"))
        layout.texts.append(Text(x0 + 104, y0 + 80, pair.unit, 14, theme.text_muted))
        layout.texts.append(Text(x0 + 104, y0 + 128, pair.pair, 12, theme.text_dim))

        snapshot = values.get(code)
        if snapshot is None:
            layout.texts.append(Text(x1 - 28, y0 + 58, "—", 26, theme.text_dim, "bold", "end"))
        else:
            price, change = snapshot
            layout.texts.append(
                Text(x1 - 28, y0 + 58, price_text(price, pair.symbol), 26, theme.text, "bold", "end")
            )
            kind = delta_kind(change)
            tint = {"up": theme.up, "down": theme.down, "flat": theme.flat}[kind]
            layout.texts.append(Text(x1 - 28, y0 + 84, change_text(change), 14, tint, "bold", "end"))

    layout.texts.append(
        Text(64.0, 580.0, "Данные обновляются каждую минуту · история хранится в PostgreSQL", 15, theme.text_dim)
    )
    layout.texts.append(Text(1216.0, 580.0, "fxbot", 15, theme.text_dim, "bold", "end"))
    return layout
