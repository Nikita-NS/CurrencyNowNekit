"""Графики: расчёт геометрии + два рендера (SVG и PNG)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import tzinfo

from PIL import Image

from .model import (
    ChartSpec,
    Layout,
    Point,
    SeriesInput,
    build_layout,
    fmt_num,
    fmt_pct,
    price_decimals,
)
from .png import encode_png, render_hd_png, render_image, render_png
from .svg import render_svg

__all__ = [
    "ChartSpec",
    "Layout",
    "Point",
    "SeriesInput",
    "build_layout",
    "fmt_num",
    "fmt_pct",
    "price_decimals",
    "RenderedChart",
    "render_chart",
    "encode_png",
    "render_hd_png",
    "render_image",
    "render_png",
    "render_svg",
]


@dataclass(frozen=True)
class RenderedChart:
    png: bytes       # 1280x720 — уходит в чат фотографией (Telegram пережмёт в JPEG)
    hd_png: bytes    # 2560x1440 — уходит документом, без сжатия
    svg: str
    layout: Layout


def render_chart(spec: ChartSpec, period_seconds: int, tick_seconds: int, tz: tzinfo) -> RenderedChart:
    """Считает геометрию один раз и отдаёт все три версии картинки.

    Крупная картинка рисуется один раз: обычная — это та же картинка,
    уменьшенная вдвое (сглаживание), поэтому они гарантированно совпадают.
    """
    layout = build_layout(spec, period_seconds=period_seconds, tick_seconds=tick_seconds, tz=tz)
    big = render_image(layout, scale=2, downscale=False)
    small = big.resize((layout.width, layout.height), Image.LANCZOS)
    return RenderedChart(
        png=encode_png(small),
        hd_png=encode_png(big),
        svg=render_svg(layout),
        layout=layout,
    )
