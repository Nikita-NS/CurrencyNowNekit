"""Фоновый поллер: раз в минуту снимает курсы и складывает их в PostgreSQL."""

from __future__ import annotations

import asyncio
import logging
import time

from .rates import RateService

log = logging.getLogger(__name__)

ROLLUP_EVERY = 3600.0  # пересчёт дневной агрегации раз в час


async def poller_loop(rates: RateService, interval: int, stop: asyncio.Event) -> None:
    try:
        await rates.warmup()
    except Exception:  # noqa: BLE001 - прогрев не должен убивать поллер
        log.exception("Прогрев истории не удался")

    last_rollup = 0.0
    while not stop.is_set():
        started = time.monotonic()
        try:
            count = await rates.snapshot()
            if count:
                log.info("Снимок курсов: %s пар", count)
        except Exception:  # noqa: BLE001
            log.exception("Ошибка опроса курсов")

        if time.monotonic() - last_rollup >= ROLLUP_EVERY:
            last_rollup = time.monotonic()
            try:
                days = await rates.rollup(2)
                log.info("daily_stats пересчитан: %s строк", days)
            except Exception:  # noqa: BLE001
                log.exception("Ошибка агрегации daily_stats")

        delay = max(5.0, interval - (time.monotonic() - started))
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
            return
        except asyncio.TimeoutError:
            continue
