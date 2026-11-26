"""Сервис курсов: решает, откуда взять ряд (PostgreSQL или провайдер)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from ..charts.model import Point
from ..pairs import PAIRS, PAIR_ORDER, PERIODS, PairDef, PeriodDef
from ..providers.base import Bar, ProviderError, RateProvider

if TYPE_CHECKING:  # чтобы модуль импортировался без asyncpg (тесты, превью)
    from ..db.repo import Repo

log = logging.getLogger(__name__)


@dataclass
class SeriesResult:
    pair: PairDef
    period: PeriodDef
    points: list[Point]
    source: str
    db_rows: int = 0


class RateService:
    def __init__(
        self,
        repo: Repo | None,
        provider: RateProvider,
        tz: ZoneInfo,
        tz_name: str = "Europe/Moscow",
        poll_interval: int = 60,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.tz = tz
        self.tz_name = tz_name
        self.poll_interval = poll_interval

    # ------------------------------------------------------------------
    # Ряды для графиков
    # ------------------------------------------------------------------
    async def series(self, pair: PairDef, period: PeriodDef) -> SeriesResult:
        if period.from_daily:
            return await self._daily_series(pair, period)
        return await self._tick_series(pair, period)

    async def _tick_series(self, pair: PairDef, period: PeriodDef) -> SeriesResult:
        now = datetime.now(self.tz).replace(second=0, microsecond=0)
        since = now - timedelta(seconds=period.seconds)
        rows: list[tuple[datetime, float]] = []
        if self.repo is not None:
            try:
                rows = await self.repo.ticks(pair.pair, since.astimezone(timezone.utc))
            except Exception:  # noqa: BLE001 - БД не должна ронять график
                log.exception("Не удалось прочитать тики %s из БД", pair.pair)

        if rows and self._covers(rows[0][0], rows[-1][0], period.seconds) and len(rows) >= 10:
            points = [Point(ts, value) for ts, value in rows]
            return SeriesResult(pair, period, points, "PostgreSQL", len(points))

        try:
            points = await self.provider.history(pair, period)
        except ProviderError:
            if rows:
                log.warning("Провайдер недоступен, отдаю %s из БД (%s точек)", pair.pair, len(rows))
                return SeriesResult(
                    pair, period, [Point(ts, value) for ts, value in rows],
                    "PostgreSQL (неполные данные)", len(rows),
                )
            raise

        await self._store_ticks(pair, points)
        # провайдер отдаёт окно шире запрошенного (например 2 дня на «24 часа») —
        # обрезаем, чтобы график и подпись говорили про один и тот же период
        window = [p for p in points if p.ts >= since]
        if len(window) < 3:
            window = points
        return SeriesResult(pair, period, window, self.provider.name, len(rows))

    async def _daily_series(self, pair: PairDef, period: PeriodDef) -> SeriesResult:
        now = datetime.now(self.tz)
        since_day: date = (now - timedelta(seconds=period.seconds)).date()
        period_days = max(1, period.seconds // 86400)
        rows: list[tuple[date, float]] = []
        if self.repo is not None:
            try:
                rows = await self.repo.daily(pair.pair, since_day)
            except Exception:  # noqa: BLE001
                log.exception("Не удалось прочитать daily_stats %s", pair.pair)

        enough = len(rows) >= 3 and (rows[-1][0] - rows[0][0]).days >= period_days * 0.7
        if enough:
            points = [Point(datetime.combine(day, time(23, 59), tzinfo=self.tz), close)
                      for day, close in rows]
            return SeriesResult(pair, period, points, "PostgreSQL", len(points))

        try:
            points = await self.provider.history(pair, period)
        except ProviderError:
            if rows:
                points = [Point(datetime.combine(day, time(23, 59), tzinfo=self.tz), close)
                          for day, close in rows]
                return SeriesResult(pair, period, points, "PostgreSQL (неполные данные)", len(points))
            raise

        # у провайдера могут быть настоящие свечи (open/high/low/close) — берём их,
        # иначе в daily_stats не будет дневного диапазона
        bars = await self._daily_bars(pair, period)
        if len(bars) >= 2:
            await self._store_bars(pair, bars)
            points = [Point(bar.ts, bar.close) for bar in bars]
            window = [p for p in points if p.ts.astimezone(self.tz).date() >= since_day]
            if len(window) < 3:
                window = points
            return SeriesResult(pair, period, window, self.provider.name, len(rows))

        await self._store_daily(pair, points)
        window = [p for p in points if p.ts.astimezone(self.tz).date() >= since_day]
        if len(window) < 3:
            window = points
        return SeriesResult(pair, period, window, self.provider.name, len(rows))

    async def _daily_bars(self, pair: PairDef, period: PeriodDef) -> list[Bar]:
        try:
            return await self.provider.daily_bars(pair, period)
        except ProviderError:
            return []
        except Exception:  # noqa: BLE001 - свечи не должны ронять график
            log.exception("Не удалось получить дневные свечи %s", pair.pair)
            return []

    @staticmethod
    def _covers(first: datetime, last: datetime, period_seconds: int) -> bool:
        return (last - first).total_seconds() >= period_seconds * 0.7

    # ------------------------------------------------------------------
    # Запись в БД
    # ------------------------------------------------------------------
    async def _store_ticks(self, pair: PairDef, points: list[Point]) -> None:
        if self.repo is None or not points:
            return
        try:
            rows = [(pair.pair, point.ts, point.value, "backfill") for point in points]
            inserted = await self.repo.upsert_ticks(rows)
            log.debug("Бэкфилл %s: %s новых точек", pair.pair, inserted)
        except Exception:  # noqa: BLE001
            log.exception("Не удалось сохранить тики %s", pair.pair)

    async def _store_bars(self, pair: PairDef, bars: list[Bar]) -> None:
        """Пишет настоящие свечи: open/high/low/close + изменение за день."""
        if self.repo is None or not bars:
            return
        rows = [
            (
                pair.pair,
                bar.ts.astimezone(self.tz).date(),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.change_pct,
                1,
                self.provider.name,
            )
            for bar in bars
        ]
        try:
            saved = await self.repo.upsert_daily(rows)
            log.debug("Свечи %s: %s дней", pair.pair, saved)
        except Exception:  # noqa: BLE001
            log.exception("Не удалось сохранить свечи %s", pair.pair)

    async def _store_daily(self, pair: PairDef, points: list[Point]) -> None:
        if self.repo is None or not points:
            return
        buckets: dict[date, list[Point]] = {}
        for point in points:
            buckets.setdefault(point.ts.astimezone(self.tz).date(), []).append(point)

        rows = []
        for day in sorted(buckets):
            values = sorted(buckets[day], key=lambda p: p.ts)
            open_price = values[0].value
            close_price = values[-1].value
            change = 0.0 if open_price == 0 else (close_price / open_price - 1) * 100
            rows.append(
                (
                    pair.pair,
                    day,
                    open_price,
                    max(p.value for p in values),
                    min(p.value for p in values),
                    close_price,
                    change,
                    len(values),
                    self.provider.name,
                )
            )
        try:
            await self.repo.upsert_daily(rows)
        except Exception:  # noqa: BLE001
            log.exception("Не удалось сохранить daily_stats %s", pair.pair)

    # ------------------------------------------------------------------
    # Поллер и агрегация
    # ------------------------------------------------------------------
    async def snapshot(self) -> int:
        """Снимает текущие курсы всех валют и пишет их в rate_ticks."""
        now = datetime.now(self.tz).replace(second=0, microsecond=0)
        pairs = [PAIRS[code] for code in PAIR_ORDER]
        results = await asyncio.gather(
            *(self.provider.latest(pair) for pair in pairs), return_exceptions=True
        )
        rows: list[tuple[str, datetime, float, str]] = []
        for pair, result in zip(pairs, results):
            if isinstance(result, BaseException):
                log.warning("Нет курса %s: %s", pair.pair, result)
                continue
            if result and result > 0:
                rows.append((pair.pair, now, float(result), "poll"))
        if rows and self.repo is not None:
            await self.repo.upsert_ticks(rows)
        return len(rows)

    async def latest_map(self) -> dict[str, float]:
        """Текущие курсы для карточки меню (ошибки просто пропускаем)."""
        pairs = [PAIRS[code] for code in PAIR_ORDER]
        results = await asyncio.gather(
            *(self.provider.latest(pair) for pair in pairs), return_exceptions=True
        )
        out: dict[str, float] = {}
        for pair, result in zip(pairs, results):
            if isinstance(result, BaseException) or not result:
                continue
            out[pair.code] = float(result)
        return out

    async def menu_values(self) -> dict[str, tuple[float, float]]:
        """Пары (цена, изменение за час в %) — для плиток меню."""
        prices = await self.latest_map()
        out: dict[str, tuple[float, float]] = {}
        for code, price in prices.items():
            change = 0.0
            if self.repo is not None:
                try:
                    rows = await self.repo.ticks(
                        PAIRS[code].pair,
                        (datetime.now(self.tz) - timedelta(hours=1)).astimezone(timezone.utc),
                    )
                    if len(rows) >= 2:
                        change = (price / rows[0][1] - 1) * 100
                except Exception:  # noqa: BLE001
                    pass
            out[code] = (price, change)
        return out

    async def rollup(self, days: int = 2) -> int:
        if self.repo is None:
            return 0
        now = datetime.now(self.tz)
        start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            return await self.repo.rollup(
                start.astimezone(timezone.utc),
                (now + timedelta(minutes=5)).astimezone(timezone.utc),
                self.tz_name,
            )
        except Exception:  # noqa: BLE001
            log.exception("Не удалось пересчитать daily_stats")
            return 0

    async def backfill_daily(self, pair: PairDef, period_code: str = "30d") -> int:
        """Подтягивает дневную историю у провайдера, чтобы графики «7/30 дней» были не пустыми."""
        period = PERIODS[period_code]

        # сначала настоящие свечи — в daily_stats попадёт дневной диапазон цен
        bars = await self._daily_bars(pair, period)
        if len(bars) >= 2:
            await self._store_bars(pair, bars)
            return len(bars)

        try:
            points = await self.provider.history(pair, period)
        except ProviderError as exc:
            log.warning("Бэкфилл %s не удался: %s", pair.pair, exc)
            return 0
        await self._store_daily(pair, points)
        return len(points)

    async def warmup(self) -> None:
        """Первый запуск: история по дням + агрегация."""
        await asyncio.gather(*(self.backfill_daily(PAIRS[code]) for code in PAIR_ORDER),
                             return_exceptions=True)
        await self.rollup(2)

    async def close(self) -> None:
        await self.provider.close()
