"""Сборка графиков: данные -> ChartSpec -> PNG + SVG."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..charts import ChartSpec, Point, SeriesInput, render_chart, render_png
from ..charts.menu import build_menu
from ..formatting import change_text, delta_kind, percent_change, plural, price_text
from ..pairs import PairDef, PeriodDef, get_pair, get_period
from .rates import RateService, SeriesResult

log = logging.getLogger(__name__)


@dataclass
class ChartBundle:
    png: bytes
    hd_png: bytes
    svg: str
    filename: str
    pair: PairDef
    period: PeriodDef
    points: list[Point]
    source: str
    change: float
    db_rows: int = 0
    compare_pair: PairDef | None = None
    compare_points: list[Point] = field(default_factory=list)
    compare_change: float = 0.0
    compare_source: str = ""


class ChartService:
    def __init__(self, rates: RateService, tz: ZoneInfo) -> None:
        self.rates = rates
        self.tz = tz

    # ------------------------------------------------------------------
    def _footer(self, result: SeriesResult, points: list[Point]) -> str:
        stamp = datetime.now(self.tz).strftime("%H:%M")
        count = len(points)
        return f"Данные: {result.source} · {count} {plural(count, 'точка', 'точки', 'точек')} · {stamp} МСК"

    async def single(self, code: str, period_code: str) -> ChartBundle:
        pair = get_pair(code)
        period = get_period(period_code)
        result = await self.rates.series(pair, period)
        points = result.points
        if len(points) < 2:
            raise ValueError(f"Недостаточно данных по {pair.pair} за {period.title}")

        change = percent_change(points[0].value, points[-1].value)
        last = points[-1].value
        end = datetime.now(self.tz).replace(second=0, microsecond=0)
        start = None if period.from_daily else end - timedelta(seconds=period.seconds)

        spec = ChartSpec(
            title=pair.pair,
            subtitle=f"{pair.title} · {pair.unit} · {period.title}",
            footer=self._footer(result, points),
            series=[SeriesInput(pair.pair, pair.title, pair.color, tuple(points))],
            badge=pair.code,
            badge_color=pair.color,
            value_text=price_text(last, pair.symbol),
            delta_text=change_text(change),
            delta_kind=delta_kind(change),
            start=start,
            end=None if start is None else end,
        )
        rendered = render_chart(spec, period.seconds, period.tick_seconds, self.tz)
        return ChartBundle(
            png=rendered.png,
            hd_png=rendered.hd_png,
            svg=rendered.svg,
            filename=f"{pair.code.lower()}-{period.code}",
            pair=pair,
            period=period,
            points=points,
            source=result.source,
            change=change,
            db_rows=result.db_rows,
        )

    async def compare(self, first_code: str, second_code: str, period_code: str) -> ChartBundle:
        pair_a = get_pair(first_code)
        pair_b = get_pair(second_code)
        period = get_period(period_code)
        result_a, result_b = await self._both(pair_a, pair_b, period)

        change_a = percent_change(result_a.points[0].value, result_a.points[-1].value)
        change_b = percent_change(result_b.points[0].value, result_b.points[-1].value)
        end = datetime.now(self.tz).replace(second=0, microsecond=0)
        start = None if period.from_daily else end - timedelta(seconds=period.seconds)
        sources = " + ".join(dict.fromkeys([result_a.source, result_b.source]))

        spec = ChartSpec(
            title=f"{pair_a.pair} и {pair_b.pair}",
            subtitle=f"Сравнение {period.title} · изменение в %",
            footer=self._footer(result_a, result_a.points + result_b.points)
            if result_a.source == result_b.source
            else f"Данные: {sources} · {len(result_a.points) + len(result_b.points)} точек",
            series=[
                SeriesInput(pair_a.pair, pair_a.title, pair_a.color, tuple(result_a.points)),
                SeriesInput(pair_b.pair, pair_b.title, pair_b.color, tuple(result_b.points)),
            ],
            mode="percent",
            start=start,
            end=None if start is None else end,
        )
        rendered = render_chart(spec, period.seconds, period.tick_seconds, self.tz)
        return ChartBundle(
            png=rendered.png,
            hd_png=rendered.hd_png,
            svg=rendered.svg,
            filename=f"{pair_a.code.lower()}-{pair_b.code.lower()}-{period.code}",
            pair=pair_a,
            period=period,
            points=result_a.points,
            source=result_a.source,
            change=change_a,
            db_rows=result_a.db_rows,
            compare_pair=pair_b,
            compare_points=result_b.points,
            compare_change=change_b,
            compare_source=result_b.source,
        )

    async def _both(self, pair_a: PairDef, pair_b: PairDef, period: PeriodDef):
        return await asyncio.gather(
            self.rates.series(pair_a, period),
            self.rates.series(pair_b, period),
        )

    async def menu_card(self) -> bytes:
        values: dict[str, tuple[float, float]] | None = None
        try:
            values = await self.rates.menu_values()
        except Exception:  # noqa: BLE001 - меню должно открыться даже без данных
            log.exception("Не удалось получить курсы для меню")
        return render_png(build_menu(values))
