"""Точка входа: бот + поллер + PostgreSQL."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .bot import router
from .bot.middleware import ServicesMiddleware
from .config import ConfigError, Settings
from .db import Repo, apply_schema, connect_with_retry
from .logging_setup import setup_logging
from .providers import build_provider
from .services.charts_service import ChartService
from .services.poller import poller_loop
from .services.rates import RateService

log = logging.getLogger(__name__)


async def run() -> None:
    settings = Settings.load()
    setup_logging(settings.log_level)
    log.info("Провайдер курсов: %s · часовой пояс: %s", settings.rates_provider, settings.tz_name)

    pool = None
    repo: Repo | None = None
    if settings.db_enabled:
        pool = await connect_with_retry(settings.database_url)
        await apply_schema(pool)
        repo = Repo(pool)
    else:
        log.warning("DATABASE_URL не задан: работаю без истории в PostgreSQL")

    provider = build_provider(settings)
    await provider.start()
    rates = RateService(
        repo,
        provider,
        settings.tz,
        tz_name=settings.tz_name,
        poll_interval=settings.poll_interval,
    )
    charts = ChartService(rates, settings.tz)

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(
        ServicesMiddleware(repo=repo, rates=rates, charts=charts, settings=settings)
    )
    dispatcher.include_router(router)

    stop = asyncio.Event()
    poller = asyncio.create_task(poller_loop(rates, settings.poll_interval, stop), name="poller")

    try:
        with contextlib.suppress(Exception):
            await bot.delete_webhook(drop_pending_updates=False)
        me = await bot.get_me()
        log.info("Бот @%s запущен", me.username)
        await dispatcher.start_polling(
            bot, allowed_updates=dispatcher.resolve_used_update_types()
        )
    finally:
        stop.set()
        poller.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poller
        await rates.close()
        with contextlib.suppress(Exception):
            await bot.session.close()
        if pool is not None:
            await pool.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nОстановлено пользователем")
    except ConfigError as exc:
        print(f"Ошибка конфигурации: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
