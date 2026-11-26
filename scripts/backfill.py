"""Заполняет daily_stats историей с провайдера (7 или 30 дней).

    python -m scripts.backfill --days 30

Полезно на первом запуске: графики «7 дней» и «30 дней» сразу будут
с данными, а не с тремя точками.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.config import Settings
from app.db import Repo, apply_schema, connect_with_retry
from app.pairs import PAIRS, PAIR_ORDER
from app.providers import build_provider
from app.services.rates import RateService


async def run(days: int) -> None:
    settings = Settings.load()
    if not settings.db_enabled:
        raise SystemExit("DATABASE_URL не задан — бэкфилл некуда писать")

    pool = await connect_with_retry(settings.database_url)
    await apply_schema(pool)
    provider = build_provider(settings)
    await provider.start()
    rates = RateService(
        Repo(pool), provider, settings.tz, settings.tz_name, settings.poll_interval
    )

    period_code = "7d" if days <= 7 else "30d"
    try:
        for code in PAIR_ORDER:
            pair = PAIRS[code]
            count = await rates.backfill_daily(pair, period_code)
            print(f"{pair.pair:<9} {count:>4} дневных точек")
        rows = await rates.rollup(max(days, 2))
        print(f"daily_stats пересчитан: {rows} строк")
    finally:
        await rates.close()
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Бэкфилл дневной истории курсов")
    parser.add_argument("--days", type=int, default=30, help="сколько дней истории тянуть")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.days))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
