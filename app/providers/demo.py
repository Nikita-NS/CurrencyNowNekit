"""Демо-источник: правдоподобные ряды без сети.

Нужен, чтобы запустить бота и посмотреть интерфейс до подключения биржевого
API (``RATES_PROVIDER=demo``). Значение в каждой минуте детерминированно,
поэтому поллер и график видят одинаковые цифры.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta

from ..charts.model import Point
from ..pairs import PairDef, PeriodDef
from .base import RateProvider

BASE_PRICES: dict[str, float] = {
    "USD/RUB": 82.19,
    "EUR/RUB": 90.25,
    "CNY/RUB": 12.33,
    "RUB/USD": 1 / 82.19,
}

STEP_BY_PERIOD: dict[str, int] = {"1h": 60, "24h": 900, "7d": 86400, "30d": 86400}


def _seed(key: str) -> int:
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:6], "big")


def value_at(pair: str, moment: datetime) -> float:
    base = BASE_PRICES.get(pair, 1.0)
    stamp = moment.timestamp()
    phase = (_seed(pair) % 1000) / 1000 * 2 * math.pi

    slow = math.sin(stamp / 7200 + phase) * 0.0022
    medium = math.sin(stamp / 1500 + phase * 1.7) * 0.0009
    fast = math.sin(stamp / 240 + phase * 2.3) * 0.0003
    jitter = ((_seed(f"{pair}:{int(stamp // 60)}") % 2000) / 1000 - 1) * 0.00035

    return round(base * (1.0 + slow + medium + fast + jitter), 6)


class DemoProvider(RateProvider):
    name = "Демо-данные"

    def __init__(self, tz) -> None:
        self._tz = tz

    async def history(self, pair: PairDef, period: PeriodDef) -> list[Point]:
        step = STEP_BY_PERIOD.get(period.code, 300)
        count = max(8, min(400, period.seconds // step + 1))
        end = datetime.now(self._tz).replace(second=0, microsecond=0)
        start = end - timedelta(seconds=step * (count - 1))
        return [Point(start + timedelta(seconds=step * i), value_at(pair.pair, start + timedelta(seconds=step * i)))
                for i in range(count)]

    async def latest(self, pair: PairDef) -> float:
        return value_at(pair.pair, datetime.now(self._tz))
