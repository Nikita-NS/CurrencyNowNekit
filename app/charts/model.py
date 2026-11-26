"""Расчёт геометрии графика.

Модуль не зависит от библиотек рисования: он строит *список примитивов*
(прямоугольники, линии, полилинии, точки, тексты) в дизайнерских координатах
1280x720. Дальше ``svg.py`` и ``png.py`` просто рисуют эти примитивы, поэтому
SVG-файл и PNG-картинка выглядят одинаково.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, tzinfo
from typing import Iterable, Literal

from .theme import THEME, Theme

DESIGN_W = 1280
DESIGN_H = 720

PLOT_LEFT = 60.0
PLOT_RIGHT = 1186.0
PLOT_TOP = 210.0
PLOT_BOTTOM = 592.0
X_INSET = 16.0

#: Минимальное расстояние между подписями времени: чем больше, тем их меньше,
#: а значит крупнее и читаемее на экране телефона.
MIN_LABEL_GAP = 96.0

MINUS = "\u2212"
NBSP = "\u00a0"

# --------------------------------------------------------------------------
# Примитивы
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    text: str
    size: int
    color: str
    weight: Literal["normal", "bold"] = "normal"
    anchor: Literal["start", "middle", "end"] = "start"


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float
    fill: str | None = None
    alpha: float = 1.0
    radius: float = 0.0
    stroke: str | None = None
    stroke_width: float = 1.0


@dataclass(frozen=True)
class Line:
    x0: float
    y0: float
    x1: float
    y1: float
    color: str
    width: float = 1.0
    alpha: float = 1.0
    dash: tuple[float, float] | None = None


@dataclass(frozen=True)
class Polyline:
    points: tuple[tuple[float, float], ...]
    color: str
    width: float = 3.0
    alpha: float = 1.0
    closed: bool = False


@dataclass(frozen=True)
class Area:
    points: tuple[tuple[float, float], ...]
    color: str
    alpha: float = 0.5
    fade_from: float = 0.0
    fade_to: float = 0.0


@dataclass(frozen=True)
class Dot:
    x: float
    y: float
    r: float
    color: str
    ring: str | None = None
    ring_width: float = 0.0


@dataclass
class Layout:
    width: int
    height: int
    bg_top: str
    bg_bottom: str
    texts: list[Text] = field(default_factory=list)
    rects: list[Rect] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    areas: list[Area] = field(default_factory=list)
    polylines: list[Polyline] = field(default_factory=list)
    dots: list[Dot] = field(default_factory=list)
    title: str = ""


# --------------------------------------------------------------------------
# Данные
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Point:
    ts: datetime
    value: float


@dataclass(frozen=True)
class SeriesInput:
    key: str
    label: str
    color: str
    points: tuple[Point, ...]


@dataclass
class ChartSpec:
    title: str
    subtitle: str
    footer: str
    series: list[SeriesInput]
    mode: Literal["price", "percent"] = "price"
    badge: str | None = None
    badge_color: str = "#5B9DFF"
    value_text: str | None = None
    delta_text: str | None = None
    delta_kind: Literal["up", "down", "flat"] = "flat"
    start: datetime | None = None
    end: datetime | None = None
    theme: Theme = THEME


# --------------------------------------------------------------------------
# Форматирование
# --------------------------------------------------------------------------


def fmt_num(value: float, decimals: int) -> str:
    """82.19 -> '82,19' (русская запись, неразрывный пробел между тысячами)."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", NBSP).replace(".", ",")


def fmt_pct(value: float, decimals: int = 2) -> str:
    sign = "+" if value > 0 else (MINUS if value < 0 else "")
    return f"{sign}{fmt_num(abs(value), decimals)}{NBSP}%"


def pct_decimals(span: float) -> int:
    if span < 0.5:
        return 2
    if span < 5:
        return 1
    return 1


def price_decimals(lo: float, hi: float) -> int:
    span = max(abs(hi - lo), 1e-12)
    step = span / 5
    decimals = -int(math.floor(math.log10(step))) + 1
    decimals = max(0, min(6, decimals))
    if abs(hi) < 0.01:
        decimals = max(decimals, 5)
    elif abs(hi) < 1:
        decimals = max(decimals, 4)
    return decimals


def decimals_for_step(step: float) -> int:
    step = abs(step)
    if step <= 0:
        return 2
    exponent = math.floor(math.log10(step))
    mantissa = step / (10 ** exponent)
    decimals = -int(exponent)
    if abs(mantissa - 2.5) < 1e-9:
        decimals += 1
    return max(0, min(6, decimals))


def estimate_text_width(text: str, size: int, bold: bool = False) -> float:
    """Грубая ширина строки (для расчёта плашек/легенды)."""
    narrow = " .,:;!|'"
    wide = "▲▼■−+%"
    units = 0.0
    for ch in text:
        if ch in narrow:
            units += 0.28
        elif ch in wide:
            units += 0.62
        elif ch.isupper():
            units += 0.66
        elif ch.isdigit():
            units += 0.56
        else:
            units += 0.56
    return units * size * (1.03 if bold else 1.0)


# --------------------------------------------------------------------------
# Тики
# --------------------------------------------------------------------------


def nice_step(span: float, target: int = 5) -> float:
    if span <= 0:
        return 1.0
    raw = span / max(target, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    for mult in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= mult * magnitude:
            return mult * magnitude
    return 10.0 * magnitude


def nice_ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    if hi <= lo:
        hi = lo + max(abs(lo) * 0.001, 1e-6)
    step = nice_step(hi - lo, target)
    start = math.ceil(lo / step - 1e-9) * step
    ticks: list[float] = []
    value = start
    while value <= hi + step * 1e-6 and len(ticks) < 12:
        ticks.append(round(value, 10))
        value += step
    if len(ticks) < 2:
        ticks = [lo, hi]
    return ticks


def _align_time(start: datetime, step: int, tz: tzinfo) -> datetime:
    """Первый тик сетки, не раньше start."""
    local = start.astimezone(tz)
    if step >= 86400:
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight if midnight >= local else midnight + timedelta(days=1)
    epoch = int(local.timestamp())
    aligned_epoch = (epoch // step) * step
    if aligned_epoch < epoch:
        aligned_epoch += step
    return datetime.fromtimestamp(aligned_epoch, tz=tz)


def time_ticks(start: datetime, end: datetime, step: int, tz: tzinfo) -> list[datetime]:
    ticks: list[datetime] = []
    cursor = _align_time(start, step, tz)
    guard = 0
    while cursor < end and guard < 60:
        ticks.append(cursor)
        cursor += timedelta(seconds=step)
        guard += 1
    if len(ticks) < 2:
        mid = start + (end - start) / 2
        ticks = [start + (end - start) * 0.25, mid, end - (end - start) * 0.25]
    return ticks


def _fmt_time_axis(moment: datetime, step: int, tz: tzinfo) -> str:
    local = moment.astimezone(tz)
    if step >= 86400:
        return local.strftime("%d.%m")
    return local.strftime("%H:%M")


# --------------------------------------------------------------------------
# Построение
# --------------------------------------------------------------------------


def _clip(points: Iterable[Point], start: datetime, end: datetime) -> list[Point]:
    ordered = sorted(points, key=lambda p: p.ts)
    return [p for p in ordered if start <= p.ts <= end]


def _to_percent(points: list[Point]) -> list[Point]:
    if not points:
        return []
    base = points[0].value
    if base == 0:
        return [Point(p.ts, 0.0) for p in points]
    return [Point(p.ts, (p.value / base - 1.0) * 100.0) for p in points]


def build_layout(spec: ChartSpec, period_seconds: int, tick_seconds: int, tz: tzinfo) -> Layout:
    theme = spec.theme
    layout = Layout(width=DESIGN_W, height=DESIGN_H, bg_top=theme.bg_top, bg_bottom=theme.bg_bottom)
    layout.title = spec.title

    if not spec.series:
        raise ValueError("ChartSpec.series пуст")

    all_stamps = [p.ts for s in spec.series for p in s.points]
    if not all_stamps:
        raise ValueError("Нет данных для графика")

    end = spec.end or max(all_stamps)
    start = spec.start or (end - timedelta(seconds=period_seconds))

    inside = sum(len(_clip(s.points, start, end)) for s in spec.series)
    if inside < 3:
        # окно почти пустое (источник отдал данные с задержкой) — показываем
        # всё, что есть, вместо двух точек на пустом графике
        start, end = min(all_stamps), max(all_stamps)
        if end <= start:
            end = start + timedelta(minutes=1)

    plotted: list[tuple[SeriesInput, list[Point]]] = []
    for series in spec.series:
        points = _clip(series.points, start, end)
        if spec.mode == "percent":
            points = _to_percent(points)
        if len(points) == 1:
            points = [points[0], Point(points[0].ts + timedelta(seconds=1), points[0].value)]
        if points:
            plotted.append((series, points))

    if not plotted:
        raise ValueError("Нет данных в выбранном окне")

    data_start = min(p[0].ts for _, p in plotted)
    data_end = max(p[-1].ts for _, p in plotted)
    if (data_end - data_start).total_seconds() < period_seconds * 0.5:
        start, end = data_start, max(data_end, data_start + timedelta(minutes=1))
    span_seconds = max((end - start).total_seconds(), 1.0)

    values = [p.value for _, points in plotted for p in points]
    lo, hi = min(values), max(values)
    if spec.mode == "percent":
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    if math.isclose(lo, hi):
        pad = max(abs(hi) * 0.002, 1e-6 if spec.mode == "price" else 0.05)
        lo, hi = lo - pad, hi + pad
    pad = (hi - lo) * 0.10
    lo, hi = lo - pad, hi + pad

    ticks = nice_ticks(lo, hi, 5)
    lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])

    def x_of(moment: datetime) -> float:
        inner = PLOT_RIGHT - PLOT_LEFT - 2 * X_INSET
        return PLOT_LEFT + X_INSET + (moment - start).total_seconds() / span_seconds * inner

    def y_of(value: float) -> float:
        return PLOT_BOTTOM - (value - lo) / (hi - lo) * (PLOT_BOTTOM - PLOT_TOP)

    # --- заголовок -------------------------------------------------------
    if spec.badge:
        layout.rects.append(Rect(60.0, 52.0, 120.0, 112.0, fill=spec.badge_color, radius=30.0))
        layout.texts.append(
            Text(90.0, 91.0, spec.badge, 17, theme.white, "bold", "middle")
        )
        title_x = 136.0
    else:
        title_x = PLOT_LEFT

    layout.texts.append(Text(title_x, 94.0, spec.title, 36, theme.text, "bold"))
    layout.texts.append(Text(title_x, 128.0, spec.subtitle, 20, theme.text_muted))

    if spec.value_text:
        layout.texts.append(Text(1220.0, 88.0, spec.value_text, 48, theme.text, "bold", "end"))
    if spec.delta_text:
        color = {"up": theme.up, "down": theme.down, "flat": theme.flat}[spec.delta_kind]
        width = estimate_text_width(spec.delta_text, 20, True) + 34
        top = 104.0
        layout.rects.append(
            Rect(1220.0 - width, top, 1220.0, top + 36.0, fill=color, alpha=0.18, radius=18.0)
        )
        layout.texts.append(
            Text(1220.0 - width / 2, top + 25.0, spec.delta_text, 20, color, "bold", "middle")
        )

    # --- легенда для сравнения ------------------------------------------
    if len(plotted) > 1:
        chip_x = PLOT_LEFT
        for index, (series, points) in enumerate(plotted):
            delta = points[-1].value - points[0].value
            label = f"{series.key}  {fmt_pct(delta, 2)}"
            width = estimate_text_width(label, 19, True) + 52
            layout.rects.append(
                Rect(chip_x, 146.0, chip_x + width, 182.0, fill=theme.panel_soft, radius=18.0,
                     stroke=theme.border, stroke_width=1.0)
            )
            layout.dots.append(Dot(chip_x + 20.0, 164.0, 6.0, series.color))
            layout.texts.append(
                Text(chip_x + 36.0, 171.0, label, 19, theme.text, "bold")
            )
            chip_x += width + 14.0
            if chip_x > PLOT_RIGHT - 120:
                break

    # --- сетка -----------------------------------------------------------
    layout.lines.append(
        Line(PLOT_LEFT, PLOT_BOTTOM, PLOT_RIGHT, PLOT_BOTTOM, theme.axis, 1.4, 1.0)
    )
    step = ticks[1] - ticks[0] if len(ticks) > 1 else max(ticks[-1] - ticks[0], 1.0)
    for tick in ticks:
        y = y_of(tick)
        strong = spec.mode == "percent" and abs(tick) < 1e-9
        # сплошные линии вместо пунктира: пунктир в JPEG расплывается в грязь
        layout.lines.append(
            Line(
                PLOT_LEFT,
                y,
                PLOT_RIGHT,
                y,
                theme.zero if strong else theme.grid,
                1.6 if strong else 1.0,
                0.9 if strong else 0.55,
            )
        )
        if spec.mode == "percent":
            label = fmt_pct(tick, 1 if abs(step) >= 0.05 else 2)
        else:
            decimals = decimals_for_step(step)
            if decimals == 0 and abs(hi) < 1000:
                decimals = 1  # 82,0 читается лучше, чем 82
            label = fmt_num(tick, decimals)
        layout.texts.append(Text(1276.0, y + 6.0, label, 18, theme.text_muted, "normal", "end"))

    # --- ось X -----------------------------------------------------------
    last_label_x = -1e9
    for moment in time_ticks(start, end, tick_seconds, tz):
        x = x_of(moment)
        if x < PLOT_LEFT - 2 or x > PLOT_RIGHT + 2:
            continue
        if x - last_label_x < MIN_LABEL_GAP:
            continue
        last_label_x = x
        layout.lines.append(Line(x, PLOT_BOTTOM, x, PLOT_BOTTOM + 7.0, theme.axis, 1.4, 1.0))
        layout.texts.append(
            Text(x, PLOT_BOTTOM + 32.0, _fmt_time_axis(moment, tick_seconds, tz),
                 18, theme.text_dim, "normal", "middle")
        )

    # --- series ----------------------------------------------------------
    single = len(plotted) == 1
    for series, points in plotted:
        coords = tuple((x_of(p.ts), y_of(p.value)) for p in points)
        if single and spec.mode == "price":
            baseline = PLOT_BOTTOM
            area_points = coords + ((coords[-1][0], baseline), (coords[0][0], baseline))
            layout.areas.append(
                Area(
                    area_points,
                    series.color,
                    0.45,
                    fade_from=min(y for _, y in coords),
                    fade_to=baseline,
                )
            )
        # лёгкий «ореол» под линией убран: в JPEG он превращается в мыло
        layout.polylines.append(Polyline(coords, series.color, 4.2, 1.0))
        layout.dots.append(Dot(coords[-1][0], coords[-1][1], 7.0, series.color, theme.bg_top, 3.5))

    # --- подписи ----------------------------------------------------------
    layout.texts.append(Text(PLOT_LEFT, 672.0, spec.footer, 16, theme.text_dim))
    layout.texts.append(Text(1220.0, 672.0, "fxbot", 16, theme.text_dim, "bold", "end"))
    return layout
