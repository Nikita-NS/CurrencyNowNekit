"""Подключение к PostgreSQL."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import asyncpg

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def connect_with_retry(
    dsn: str, attempts: int = 15, delay: float = 2.0
) -> asyncpg.Pool:
    """Терпеливо ждёт Postgres (актуально для docker-compose)."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            pool = await asyncpg.create_pool(
                dsn, min_size=1, max_size=6, command_timeout=30
            )
            log.info("PostgreSQL подключён (попытка %s)", attempt)
            return pool
        except Exception as exc:  # noqa: BLE001 - ждём любой сбой соединения
            last_error = exc
            log.warning("PostgreSQL недоступен (%s/%s): %s", attempt, attempts, exc)
            await asyncio.sleep(delay)
    raise RuntimeError(f"Не удалось подключиться к PostgreSQL: {last_error}")


async def apply_schema(pool: asyncpg.Pool, path: Path = SCHEMA_PATH) -> None:
    sql = path.read_text(encoding="utf-8")
    async with pool.acquire() as connection:
        await connection.execute(sql)
    log.info("Схема БД применена: %s", path.name)
