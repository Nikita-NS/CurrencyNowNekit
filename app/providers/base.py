"""Интерфейс источника курсов."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ..charts.model import Point
from ..pairs import PairDef, PeriodDef


class ProviderError(RuntimeError):
    """Источник недоступен или вернул мусор."""


@dataclass(frozen=True)
class Bar:
    """Дневная (или свёрнутая из часовых) свеча — из неё считаются open/high/low/close."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float

    @property
    def change_pct(self) -> float:
        if self.open == 0:
            return 0.0
        return (self.close / self.open - 1.0) * 100.0

    @property
    def has_range(self) -> bool:
        """Есть ли у свечи реальный разброс цен внутри дня."""
        return self.high > self.low


class RateProvider(ABC):
    #: как называть источник в подписи к графику
    name: str = "provider"

    async def start(self) -> None:  # pragma: no cover - переопределяется при необходимости
        return None

    async def close(self) -> None:  # pragma: no cover
        return None

    @abstractmethod
    async def history(self, pair: PairDef, period: PeriodDef) -> list[Point]:
        """Ряд точек (цена quote за 1 base) за период."""

    @abstractmethod
    async def latest(self, pair: PairDef) -> float:
        """Текущая цена пары."""

    async def daily_bars(self, pair: PairDef, period: PeriodDef) -> list[Bar]:
        """Дневные свечи, если источник их умеет. По умолчанию — не умеет.

        Нужны для таблицы ``daily_stats``: без них движение по дням
        вырождается (open = high = low = close, изменение 0%).
        """
        return []
