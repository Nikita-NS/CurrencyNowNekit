"""Yahoo Finance: внутридневные и дневные ряды без API-ключа.

Используется публичный endpoint графика:
``https://query1.finance.yahoo.com/v8/finance/chart/USDRUB=X?interval=5m&range=1d``
Он отдаёт массивы timestamp + close, этого достаточно для графика.
"""

from __future__ import annotations

import asyncio
import time
from zoneinfo import ZoneInfo

import aiohttp

from ..charts.model import Point
from ..pairs import AUX_PAIRS, PairDef, PeriodDef
from .base import Bar, ProviderError, RateProvider
from .yahoo_parse import (
    aggregate_bars_daily,
    aggregate_daily,
    derive_series,
    invert_bars,
    parse_bars,
    parse_chart,
)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 fxbot/1.0"
)

#: Yahoo отдаёт по некоторым парам (например CNYRUB=X) всего одну дневную
#: свечу. Тогда дневной ряд собираем сами из часовых данных за этот диапазон.
INTRADAY_FALLBACK_RANGE: dict[str, str] = {"7d": "1mo", "30d": "3mo"}


class YahooProvider(RateProvider):
    name = "Yahoo Finance"

    def __init__(
        self, timeout: float = 12.0, cache_ttl: float = 15.0, tz: ZoneInfo | None = None
    ) -> None:
        self._timeout = timeout
        self._cache_ttl = cache_ttl
        self._tz = tz or ZoneInfo("UTC")
        self._session: aiohttp.ClientSession | None = None
        self._cache: dict[tuple[str, str, str], tuple[float, list[Point]]] = {}
        self._bars_cache: dict[tuple[str, str, str], tuple[float, list[Bar]]] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._session is not None and not self._session.closed:
            return
        # блокировка: при старте прогрева несколько корутин зовут start()
        # одновременно, и без неё создавалось несколько сессий (утечка).
        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                    headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    # ------------------------------------------------------------------
    async def _request(self, symbol: str, interval: str, span: str) -> dict:
        await self.start()
        assert self._session is not None
        try:
            async with self._session.get(
                CHART_URL.format(symbol=symbol),
                params={"interval": interval, "range": span, "includePrePost": "false"},
            ) as response:
                if response.status != 200:
                    raise ProviderError(f"Yahoo вернул HTTP {response.status} для {symbol}")
                return await response.json(content_type=None)
        except asyncio.TimeoutError as exc:
            raise ProviderError("Yahoo Finance не ответил вовремя") from exc
        except aiohttp.ClientError as exc:
            raise ProviderError(f"Сетевая ошибка Yahoo Finance: {exc}") from exc

    async def _fetch(self, symbol: str, interval: str, span: str) -> list[Point]:
        key = (symbol, interval, span)
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] < self._cache_ttl:
            return cached[1]
        payload = await self._request(symbol, interval, span)
        points, _ = parse_chart(payload)
        self._cache[key] = (now, points)
        return points

    async def _quote(self, symbol: str) -> float | None:
        try:
            payload = await self._request(symbol, "1h", "1d")
        except ProviderError:
            return None
        points, price = parse_chart(payload)
        if price is not None:
            return price
        return points[-1].value if points else None

    @staticmethod
    def _symbol(pair: PairDef) -> str:
        return AUX_PAIRS.get(pair.pair, pair.yahoo)

    # ------------------------------------------------------------------
    async def _fetch_bars(self, symbol: str, interval: str, span: str) -> list[Bar]:
        key = (symbol, interval, span)
        cached = self._bars_cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] < self._cache_ttl:
            return cached[1]
        payload = await self._request(symbol, interval, span)
        bars = parse_bars(payload)
        self._bars_cache[key] = (now, bars)
        return bars

    async def _direct_bars(self, pair: PairDef, interval: str, span: str) -> list[Bar]:
        """Свечи пары; для обратной пары (RUB/USD) — перевёрнутые свечи USD/RUB."""
        try:
            bars = await self._fetch_bars(self._symbol(pair), interval, span)
        except ProviderError:
            bars = []
        if bars or not pair.derive:
            return bars
        left_pair, operation, _ = pair.derive
        if operation != "invert":
            return []  # для */÷ честных high/low не построить — работаем по точкам
        try:
            left = await self._fetch_bars(AUX_PAIRS.get(left_pair, left_pair), interval, span)
        except ProviderError:
            return []
        return invert_bars(left)

    async def daily_bars(self, pair: PairDef, period: PeriodDef) -> list[Bar]:
        """Дневные свечи для daily_stats: сначала 1d, иначе сворачиваем часовые."""
        if not period.from_daily:
            return []
        bars = await self._direct_bars(pair, period.yahoo_interval, period.yahoo_range)
        if len(bars) < 3:
            fallback_range = INTRADAY_FALLBACK_RANGE.get(period.code)
            if fallback_range:
                intraday = await self._direct_bars(pair, "1h", fallback_range)
                daily = aggregate_bars_daily(intraday, self._tz)
                if len(daily) > len(bars):
                    return daily
        return bars

    # ------------------------------------------------------------------
    async def history(self, pair: PairDef, period: PeriodDef) -> list[Point]:
        points = await self._series(pair, period.yahoo_interval, period.yahoo_range, period)
        if period.from_daily and len(points) < 3:
            # у части пар Yahoo отдаёт всего одну дневную свечу — собираем день сами
            fallback_range = INTRADAY_FALLBACK_RANGE.get(period.code)
            if fallback_range:
                intraday = await self._series(pair, "1h", fallback_range, period)
                daily = aggregate_daily(intraday, self._tz)
                if len(daily) > len(points):
                    return daily
        return points

    async def _series(
        self, pair: PairDef, interval: str, span: str, period: PeriodDef
    ) -> list[Point]:
        """Ряд пары напрямую либо через кросс-курс."""
        points: list[Point] = []
        try:
            points = await self._fetch(self._symbol(pair), interval, span)
        except ProviderError:
            points = []
        if points or not pair.derive:
            if not points:
                raise ProviderError(f"Нет данных Yahoo Finance по {pair.pair}")
            return points
        return await self._derived(pair, interval, span)

    async def _derived(self, pair: PairDef, interval: str, span: str) -> list[Point]:
        assert pair.derive is not None
        left_pair, operation, right_pair = pair.derive
        left = await self._fetch(AUX_PAIRS.get(left_pair, left_pair), interval, span)
        if not left:
            raise ProviderError(f"Нет данных Yahoo Finance по {left_pair}")
        if operation == "invert":
            return derive_series(left, [], "invert")
        right = await self._fetch(AUX_PAIRS.get(right_pair, right_pair), interval, span)
        derived = derive_series(left, right, operation)
        if not derived:
            raise ProviderError(f"Не удалось посчитать кросс-курс {pair.pair}")
        return derived

    async def latest(self, pair: PairDef) -> float:
        price = await self._quote(self._symbol(pair))
        if price is not None:
            return price
        if not pair.derive:
            raise ProviderError(f"Нет котировки {pair.pair}")

        left_pair, operation, right_pair = pair.derive
        left = await self._quote(AUX_PAIRS.get(left_pair, left_pair))
        if left is None:
            raise ProviderError(f"Нет котировки {pair.pair}")
        if operation == "invert":
            return 1.0 / left
        right = await self._quote(AUX_PAIRS.get(right_pair, right_pair))
        if not right:
            raise ProviderError(f"Нет котировки {pair.pair}")
        return left * right if operation == "*" else left / right
