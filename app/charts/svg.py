"""Рендер примитивов ``model.Layout`` в standalone SVG."""

from __future__ import annotations

from xml.sax.saxutils import escape

from .model import Layout
from .theme import fonts


def _num(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _dash(dash: tuple[float, float] | None) -> str:
    if not dash:
        return ""
    return f' stroke-dasharray="{_num(dash[0])} {_num(dash[1])}"'


def _opacity(alpha: float) -> str:
    return "" if alpha >= 0.999 else f' opacity="{alpha:.3f}"'


def _attr(value: str) -> str:
    return escape(value, {'"': "&quot;", "'": "&apos;"})


def render_svg(layout: Layout) -> str:
    family = fonts().family_css
    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        f'role="img" aria-label="{_attr(layout.title)}">'
    )
    out.append(f"<title>{escape(layout.title)}</title>")
    out.append("<defs>")
    out.append(
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{layout.bg_top}"/>'
        f'<stop offset="1" stop-color="{layout.bg_bottom}"/>'
        "</linearGradient>"
    )
    for index, area in enumerate(layout.areas):
        out.append(
            f'<linearGradient id="area{index}" gradientUnits="userSpaceOnUse" '
            f'x1="0" y1="{_num(area.fade_from)}" x2="0" y2="{_num(area.fade_to)}">'
            f'<stop offset="0" stop-color="{area.color}" stop-opacity="0.55"/>'
            f'<stop offset="1" stop-color="{area.color}" stop-opacity="0"/>'
            "</linearGradient>"
        )
    out.append("</defs>")
    out.append(f'<rect width="{layout.width}" height="{layout.height}" fill="url(#bg)"/>')

    for rect in layout.rects:
        attrs = [
            f'x="{_num(rect.x0)}"',
            f'y="{_num(rect.y0)}"',
            f'width="{_num(rect.x1 - rect.x0)}"',
            f'height="{_num(rect.y1 - rect.y0)}"',
        ]
        if rect.radius:
            attrs.append(f'rx="{_num(rect.radius)}"')
        if rect.fill:
            attrs.append(f'fill="{rect.fill}"')
            if rect.alpha < 0.999:
                attrs.append(f'fill-opacity="{rect.alpha:.3f}"')
        else:
            attrs.append('fill="none"')
        if rect.stroke:
            attrs.append(f'stroke="{rect.stroke}" stroke-width="{_num(rect.stroke_width)}"')
        out.append(f"<rect {' '.join(attrs)}/>")

    for line in layout.lines:
        opacity = _opacity(line.alpha)
        out.append(
            f'<line x1="{_num(line.x0)}" y1="{_num(line.y0)}" x2="{_num(line.x1)}" '
            f'y2="{_num(line.y1)}" stroke="{line.color}" stroke-width="{_num(line.width)}"'
            f"{opacity}{_dash(line.dash)}/>"
        )

    for index, area in enumerate(layout.areas):
        points = " ".join(f"{_num(x)},{_num(y)}" for x, y in area.points)
        out.append(f'<polygon points="{points}" fill="url(#area{index})"/>')

    for poly in layout.polylines:
        points = " ".join(f"{_num(x)},{_num(y)}" for x, y in poly.points)
        out.append(
            f'<polyline points="{points}" fill="none" stroke="{poly.color}" '
            f'stroke-width="{_num(poly.width)}" stroke-linecap="round" '
            f'stroke-linejoin="round"{_opacity(poly.alpha)}/>'
        )

    for dot in layout.dots:
        ring = (
            f' stroke="{dot.ring}" stroke-width="{_num(dot.ring_width)}"'
            if dot.ring
            else ""
        )
        out.append(
            f'<circle cx="{_num(dot.x)}" cy="{_num(dot.y)}" r="{_num(dot.r)}" '
            f'fill="{dot.color}"{ring}/>'
        )

    for text in layout.texts:
        anchor = {"start": "start", "middle": "middle", "end": "end"}[text.anchor]
        weight = "700" if text.weight == "bold" else "400"
        out.append(
            f'<text x="{_num(text.x)}" y="{_num(text.y)}" fill="{text.color}" '
            f'font-family="{escape(family)}" font-size="{text.size}" '
            f'font-weight="{weight}" text-anchor="{anchor}">'
            f"{escape(text.text)}</text>"
        )

    out.append("</svg>")
    return "\n".join(out)
