"""Выбор источника курсов по настройке RATES_PROVIDER.

Импорт тяжёлых провайдеров ленивый: тесты и превью графиков не тянут aiohttp.
"""

from __future__ import annotations

from ..config import ConfigError, Settings
from .base import ProviderError, RateProvider

__all__ = ["ProviderError", "RateProvider", "build_provider"]


def build_provider(settings: Settings) -> RateProvider:
    name = settings.rates_provider
    if name in ("yahoo", "yfinance", "market"):
        from .yahoo import YahooProvider

        return YahooProvider(tz=settings.tz)
    if name in ("demo", "fake", "test"):
        from .demo import DemoProvider

        return DemoProvider(settings.tz)
    raise ConfigError(f"Неизвестный RATES_PROVIDER={name!r}. Доступно: yahoo, demo.")


def __getattr__(name: str):
    if name == "YahooProvider":
        from .yahoo import YahooProvider

        return YahooProvider
    if name == "DemoProvider":
        from .demo import DemoProvider

        return DemoProvider
    raise AttributeError(name)
