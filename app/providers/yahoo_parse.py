"""Чистые функции разбора ответа Yahoo Finance (без сети — удобно тестировать)."""

from __future__ import annotations

from datetime import date, datetime, time, timezone, tzinfo
from typing import Any

from ..charts.model import Point
from .base import Bar


def parse_chart(payload: dict[str, Any]) -> tuple[list[Point], float | None]:
    """Достаёт точки из ответа Yahoo, отбрасывая ``null`` (нет сделок в баре)."""
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        return [], None
    block = result[0] or {}
    meta = block.get("meta") or {}
    stamps = block.get("timestamp") or []
    quotes = (block.get("indicators") or {}).get("quote") or [{}]
    closes = quotes[0].get("close") or []

    points: list[Point] = []
    for stamp, value in zip(stamps, closes):
        if value is None:
            continue
        moment = datetime.fromtimestamp(int(stamp), tz=timezone.utc)
        points.append(Point(moment, float(value)))

    points.sort(key=lambda p: p.ts)
    price = meta.get("regularMarketPrice")
    return points, (float(price) if price is not None else None)


def derive_series(left: list[Point], right: list[Point], operation: str) -> list[Point]:
    """Считает кросс-курс по двум рядам, совпавшим по времени.

    operation: ``"*"``, ``"/"`` или ``"invert"`` (1/left).
    """
    if operation == "invert":
        return [Point(p.ts, 1.0 / p.value) for p in left if p.value]
    if not right:
        return []
    lookup = {p.ts: p.value for p in right}
    result: list[Point] = []
    for point in left:
        other = lookup.get(point.ts)
        if other is None or other == 0:
            continue
        if operation == "*":
            result.append(Point(point.ts, point.value * other))
        elif operation == "/":
            result.append(Point(point.ts, point.value / other))
    return result


def aggregate_daily(points: list[Point], tz: tzinfo) -> list[Point]:
    """Сворачивает внутридневной ряд в дневной (close последней точки дня).

    Смысл совпадает с ``daily_stats.close_price``: одна точка на календарный
    день в заданном часовом поясе, время — конец этого дня.
    """
    buckets: dict[date, Point] = {}
    for point in sorted(points, key=lambda p: p.ts):
        day = point.ts.astimezone(tz).date()
        buckets[day] = point  # точки идут по времени, поэтому остаётся последняя
    out: list[Point] = []
    for day in sorted(buckets):
        last = buckets[day]
        out.append(Point(datetime.combine(day, time(23, 59), tzinfo=tz), last.value))
    return out


def parse_bars(payload: dict[str, Any]) -> list[Bar]:
    """Достаёт свечи (open/high/low/close) из ответа Yahoo.

    ``null`` в close означает, что в этом баре не было сделок — такой бар
    пропускаем; отсутствующие high/low заменяем ценой закрытия.
    """
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        return []
    block = result[0] or {}
    stamps = block.get("timestamp") or []
    quotes = (block.get("indicators") or {}).get("quote") or [{}]
    quote = quotes[0] or {}
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []

    def pick(values: list[Any], index: int, fallback: float) -> float:
        if index < len(values) and values[index] is not None:
            return float(values[index])
        return fallback

    bars: list[Bar] = []
    for index, stamp in enumerate(stamps):
        close = closes[index] if index < len(closes) else None
        if close is None:
            continue
        close = float(close)
        moment = datetime.fromtimestamp(int(stamp), tz=timezone.utc)
        bars.append(
            Bar(
                ts=moment,
                open=pick(opens, index, close),
                high=pick(highs, index, close),
                low=pick(lows, index, close),
                close=close,
            )
        )
    bars.sort(key=lambda bar: bar.ts)
    return bars


def invert_bars(bars: list[Bar]) -> list[Bar]:
    """Обратная пара (USD/RUB → RUB/USD): open и close меняются местами."""
    return [
        Bar(
            ts=bar.ts,
            open=1.0 / bar.close,
            close=1.0 / bar.open,
            high=1.0 / bar.low,
            low=1.0 / bar.high,
        )
        for bar in bars
        if bar.open and bar.close and bar.high and bar.low
    ]


def aggregate_bars_daily(bars: list[Bar], tz: tzinfo) -> list[Bar]:
    """Собирает дневные свечи из часовых: open первого часа, close последнего."""
    buckets: dict[date, list[Bar]] = {}
    for bar in sorted(bars, key=lambda b: b.ts):
        buckets.setdefault(bar.ts.astimezone(tz).date(), []).append(bar)
    out: list[Bar] = []
    for day in sorted(buckets):
        group = buckets[day]
        out.append(
            Bar(
                ts=datetime.combine(day, time(23, 59), tzinfo=tz),
                open=group[0].open,
                high=max(bar.high for bar in group),
                low=min(bar.low for bar in group),
                close=group[-1].close,
            )
        )
    return out
