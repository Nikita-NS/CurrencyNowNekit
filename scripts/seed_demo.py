"""Наполняет базу демо-данными за 30 дней (без интернета).

    python -m scripts.seed_demo --days 30 --step 900

Пригодится, чтобы посмотреть графики за час/сутки/месяц, не дожидаясь,
пока поллер накопит историю.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta

from app.config import Settings
from app.db import Repo, apply_schema, connect_with_retry
from app.formatting import percent_change
from app.pairs import PAIRS, PAIR_ORDER
from app.providers.demo import value_at
from app.services.rates import RateService


async def run(days: int, step: int) -> None:
    settings = Settings.load()
    if not settings.db_enabled:
        raise SystemExit("DATABASE_URL не задан — некуда писать демо-данные")

    pool = await connect_with_retry(settings.database_url)
    await apply_schema(pool)
    repo = Repo(pool)
    tz = settings.tz

    end = datetime.now(tz).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    stamps = []
    cursor = start
    while cursor <= end:
        stamps.append(cursor.astimezone(tz))
        cursor += timedelta(seconds=step)

    total = 0
    for code in PAIR_ORDER:
        pair = PAIRS[code]
        rows = [(pair.pair, moment, value_at(pair.pair, moment), "demo") for moment in stamps]
        total += await repo.upsert_ticks(rows)
        print(f"{pair.pair:<9} +{len(rows):>6} тиков")

    rates = RateService(repo, provider=None, tz=tz, tz_name=settings.tz_name)  # type: ignore[arg-type]
    aggregated = await rates.rollup(days + 1)
    print(f"Итого тиков: {total} · строк daily_stats: {aggregated}")

    rows = await repo.daily(PAIRS["USD"].pair, (end - timedelta(days=7)).date())
    if len(rows) >= 2:
        print(
            f"USD/RUB за 7 дней: {rows[0][0]} {rows[0][1]:.2f} → "
            f"{rows[-1][0]} {rows[-1][1]:.2f} ({percent_change(rows[0][1], rows[-1][1]):+.2f}%)"
        )
    await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Демо-данные для fxbot")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--step", type=int, default=900, help="шаг тиков в секундах")
    args = parser.parse_args()
    asyncio.run(run(args.days, args.step))


if __name__ == "__main__":
    main()
