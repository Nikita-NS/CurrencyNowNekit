"""Рендер примитивов ``model.Layout`` в PNG через Pillow.

Рисуем в 2x и уменьшаем (сглаживание), чтобы линии и текст были чёткими.
"""

from __future__ import annotations

import io
import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .model import Layout
from .theme import fonts, hex_to_rgb

try:  # numpy есть в зависимостях, но рендер должен работать и без него
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore[assignment]


@lru_cache(maxsize=128)
def _font(size_px: int, bold: bool) -> ImageFont.FreeTypeFont:
    path = fonts().bold if bold else fonts().regular
    if path:
        try:
            return ImageFont.truetype(path, size_px)
        except OSError:  # повреждённый/недоступный файл шрифта
            pass
    return ImageFont.load_default(size_px)


def _gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    width, height = size
    if np is not None:
        t = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
        a = np.array(hex_to_rgb(top), dtype=np.float32)[None, :]
        b = np.array(hex_to_rgb(bottom), dtype=np.float32)[None, :]
        column = a * (1.0 - t) + b * t
        rows = np.repeat(column[:, None, :], width, axis=1)
        return Image.fromarray(rows.clip(0, 255).astype("uint8"), "RGB").convert("RGBA")

    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    r0, g0, b0 = hex_to_rgb(top)
    r1, g1, b1 = hex_to_rgb(bottom)
    for y in range(height):
        k = y / max(height - 1, 1)
        draw.line(
            [(0, y), (width, y)],
            fill=(
                round(r0 + (r1 - r0) * k),
                round(g0 + (g1 - g0) * k),
                round(b0 + (b1 - b0) * k),
            ),
        )
    return image.convert("RGBA")


def _overlay(base: Image.Image, color: str, alpha: float, draw_fn) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    if alpha < 0.999:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    base.alpha_composite(layer)


def _dashed(draw: ImageDraw.ImageDraw, p0, p1, fill, width: float, dash: tuple[float, float]) -> None:
    (x0, y0), (x1, y1) = p0, p1
    length = math.hypot(x1 - x0, y1 - y0)
    if length <= 0:
        return
    on, off = dash
    step = on + off
    pos = 0.0
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    while pos < length:
        end = min(pos + on, length)
        draw.line(
            [(x0 + ux * pos, y0 + uy * pos), (x0 + ux * end, y0 + uy * end)],
            fill=fill,
            width=max(1, round(width)),
        )
        pos += step


def render_image(layout: Layout, scale: int = 2, downscale: bool = True) -> Image.Image:
    """Рисует макет в scale раз крупнее.

    ``downscale=True`` уменьшает результат до логического размера (сглаживание);
    ``downscale=False`` отдаёт крупную картинку — она нужна для версии «без сжатия».
    """
    width, height = layout.width * scale, layout.height * scale
    base = _gradient((width, height), layout.bg_top, layout.bg_bottom)
    draw = ImageDraw.Draw(base)

    def sx(value: float) -> float:
        return value * scale

    # --- прямоугольники ---------------------------------------------------
    for rect in layout.rects:
        box = [sx(rect.x0), sx(rect.y0), sx(rect.x1), sx(rect.y1)]
        radius = sx(rect.radius)
        fill = (*hex_to_rgb(rect.fill), round(255 * rect.alpha)) if rect.fill else None
        outline = hex_to_rgb(rect.stroke) if rect.stroke else None
        if rect.alpha < 0.999 or outline:
            def paint(d: ImageDraw.ImageDraw, box=box, radius=radius, fill=fill, outline=outline, rect=rect) -> None:
                d.rounded_rectangle(
                    box,
                    radius=radius,
                    fill=fill,
                    outline=outline,
                    width=max(1, round(sx(rect.stroke_width))),
                )

            _overlay(base, rect.fill or "#000000", 1.0, paint)
        else:
            draw.rounded_rectangle(box, radius=radius, fill=fill)

    # --- линии ------------------------------------------------------------
    for line in layout.lines:
        color = (*hex_to_rgb(line.color), round(255 * line.alpha))
        if line.dash:
            _dashed(draw, (sx(line.x0), sx(line.y0)), (sx(line.x1), sx(line.y1)),
                    color, sx(line.width), (sx(line.dash[0]), sx(line.dash[1])))
        else:
            draw.line(
                [(sx(line.x0), sx(line.y0)), (sx(line.x1), sx(line.y1))],
                fill=color,
                width=max(1, round(sx(line.width))),
            )

    # --- заливка под линией ----------------------------------------------
    for area in layout.areas:
        points = [(sx(x), sx(y)) for x, y in area.points]
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).polygon(points, fill=255)
        if np is not None:
            top = sx(area.fade_from)
            bottom = sx(area.fade_to) if area.fade_to > area.fade_from else top + 1
            axis_y = np.arange(height, dtype=np.float32)[:, None]
            t = np.clip((axis_y - top) / max(bottom - top, 1.0), 0.0, 1.0)
            fade = (1.0 - t) ** 0.85
            alpha = np.asarray(mask, dtype=np.float32) * fade * area.alpha
            alpha_img = Image.fromarray(alpha.clip(0, 255).astype("uint8"), "L")
        else:  # pragma: no cover
            alpha_img = mask.point(lambda v: int(v * area.alpha))
        layer = Image.new("RGBA", (width, height), (*hex_to_rgb(area.color), 0))
        layer.putalpha(alpha_img)
        base.alpha_composite(layer)

    # --- полилинии --------------------------------------------------------
    for poly in layout.polylines:
        color = (*hex_to_rgb(poly.color), round(255 * poly.alpha))
        points = [(sx(x), sx(y)) for x, y in poly.points]
        if len(points) > 1:
            draw.line(points, fill=color, width=max(1, round(sx(poly.width))), joint="curve")

    # --- точки ------------------------------------------------------------
    for dot in layout.dots:
        r = sx(dot.r)
        box = [sx(dot.x) - r, sx(dot.y) - r, sx(dot.x) + r, sx(dot.y) + r]
        draw.ellipse(box, fill=hex_to_rgb(dot.color))
        if dot.ring:
            draw.ellipse(
                box,
                outline=hex_to_rgb(dot.ring),
                width=max(1, round(sx(dot.ring_width))),
            )

    # --- текст ------------------------------------------------------------
    anchors = {"start": "ls", "middle": "ms", "end": "rs"}
    for text in layout.texts:
        font = _font(max(8, round(text.size * scale)), text.weight == "bold")
        draw.text(
            (sx(text.x), sx(text.y)),
            text.text,
            font=font,
            fill=hex_to_rgb(text.color),
            anchor=anchors[text.anchor],
        )

    if scale > 1 and downscale:
        base = base.resize((layout.width, layout.height), Image.LANCZOS)
    return base


def encode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    # optimize=True заметно медленнее, а выигрыш в размере небольшой
    image.convert("RGB").save(buffer, format="PNG", compress_level=6)
    return buffer.getvalue()


def render_png(layout: Layout, scale: int = 2) -> bytes:
    """PNG логического размера (1280x720) — то, что уходит в чат фотографией."""
    return encode_png(render_image(layout, scale=scale, downscale=True))


def render_hd_png(layout: Layout, scale: int = 2) -> bytes:
    """PNG в scale раз крупнее — отправляется документом, без сжатия Telegram."""
    return encode_png(render_image(layout, scale=scale, downscale=False))

