"""Палитра и шрифты для рендера графиков (SVG + PNG)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Theme:
    """Цвета в формате #RRGGBB. Одна палитра на оба рендера."""

    bg_top: str = "#0D1524"
    bg_bottom: str = "#121B2E"
    panel: str = "#152134"
    panel_soft: str = "#1A2840"
    border: str = "#2A3B58"
    grid: str = "#24334D"
    axis: str = "#31435F"
    zero: str = "#456093"
    text: str = "#F5F8FD"
    text_muted: str = "#A6B6CC"
    text_dim: str = "#8A9AB0"
    up: str = "#3DDC97"
    down: str = "#FF6B81"
    flat: str = "#A6B6CC"
    white: str = "#FFFFFF"


THEME = Theme()

#: Цвет линии для каждой валюты (используется и в меню, и в графиках).
SERIES_COLORS: dict[str, str] = {
    "RUB": "#3DDC97",
    "USD": "#5B9DFF",
    "EUR": "#B18CFF",
    "CNY": "#FFB547",
}


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgba(value: str, alpha: float) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(value)
    return r, g, b, max(0, min(255, round(alpha * 255)))


@dataclass(frozen=True)
class FontSet:
    regular: str | None
    bold: str | None

    @property
    def family_css(self) -> str:
        """CSS-список шрифтов для SVG (первый доступный использует браузер).

        Имена с пробелом — в одинарных кавычках, чтобы атрибут XML остался валидным.
        """
        names = ["Segoe UI", "Arial", "DejaVu Sans", "Liberation Sans", "sans-serif"]
        return ", ".join(f"'{n}'" if " " in n or "-" in n else n for n in names)


_DEJAVU_DIRS = (
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
)

_FONT_FILES = {
    "regular": [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        *[f"{d}/DejaVuSans.ttf" for d in _DEJAVU_DIRS],
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "bold": [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        *[f"{d}/DejaVuSans-Bold.ttf" for d in _DEJAVU_DIRS],
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
}


@lru_cache(maxsize=1)
def fonts() -> FontSet:
    """Ищет шрифты с поддержкой кириллицы и ₽/€/¥."""
    found: dict[str, str | None] = {}
    for weight, candidates in _FONT_FILES.items():
        for path in candidates:
            if Path(path).is_file():
                found[weight] = path
                break
        else:
            found[weight] = None
    if found["regular"] is None and sys.platform.startswith("win"):
        # запасной вариант на Windows: любой первый .ttf из системной папки
        for path in Path("C:/Windows/Fonts").glob("*.ttf"):
            found["regular"] = str(path)
            found["bold"] = found["bold"] or str(path)
            break
    return FontSet(regular=found["regular"], bold=found["bold"] or found["regular"])
