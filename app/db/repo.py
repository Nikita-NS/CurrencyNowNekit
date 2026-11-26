"""Все SQL-запросы бота собраны здесь (asyncpg, без ORM)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Sequence

import asyncpg


def _num(value: float) -> Decimal:
    """float -> NUMERIC без сюрпризов плавающей точки."""
    return Decimal(f"{float(value):.8f}")


class Repo:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    # ------------------------------------------------------------------
    # Тики (сырые курсы)
    # ------------------------------------------------------------------
    async def upsert_ticks(
        self, rows: Sequence[tuple[str, datetime, float, str]]
    ) -> int:
        if not rows:
            return 0
        pairs = [row[0] for row in rows]
        stamps = [row[1] for row in rows]
        prices = [float(row[2]) for row in rows]
        sources = [row[3] for row in rows]
        async with self.pool.acquire() as connection:
            status = await connection.execute(
                """
                INSERT INTO rate_ticks (pair, ts, price, source)
                SELECT pair, ts, price::numeric, source
                FROM unnest($1::text[], $2::timestamptz[], $3::float8[], $4::text[])
                     AS t(pair, ts, price, source)
                ON CONFLICT (pair, ts) DO NOTHING
                """,
                pairs,
                stamps,
                prices,
                sources,
            )
        try:
            return int(status.rsplit(" ", 1)[-1])
        except ValueError:
            return 0

    async def ticks(
        self, pair: str, since: datetime, until: datetime | None = None
    ) -> list[tuple[datetime, float]]:
        if until is None:
            records = await self.pool.fetch(
                "SELECT ts, price FROM rate_ticks WHERE pair = $1 AND ts >= $2 ORDER BY ts",
                pair,
                since,
            )
        else:
            records = await self.pool.fetch(
                """
                SELECT ts, price FROM rate_ticks
                WHERE pair = $1 AND ts >= $2 AND ts <= $3
                ORDER BY ts
                """,
                pair,
                since,
                until,
            )
        return [(record["ts"], float(record["price"])) for record in records]

    # ------------------------------------------------------------------
    # Дневная агрегация
    # ------------------------------------------------------------------
    async def rollup(self, start: datetime, end: datetime, tz_name: str) -> int:
        """Пересчитывает daily_stats по тикам за [start, end)."""
        async with self.pool.acquire() as connection:
            records = await connection.fetch(
                """
                WITH agg AS (
                    SELECT pair,
                           day,
                           (array_agg(price ORDER BY ts))[1]        AS open_price,
                           max(price)                               AS high_price,
                           min(price)                               AS low_price,
                           (array_agg(price ORDER BY ts DESC))[1]   AS close_price,
                           count(*)::int                            AS points
                    FROM (
                        SELECT pair, ts, price, ((ts AT TIME ZONE $1)::date) AS day
                        FROM rate_ticks
                        WHERE ts >= $2 AND ts < $3
                    ) AS src
                    GROUP BY pair, day
                )
                INSERT INTO daily_stats (pair, day, open_price, high_price, low_price,
                                         close_price, change_pct, points, source, updated_at)
                SELECT pair, day, open_price, high_price, low_price, close_price,
                       CASE WHEN open_price = 0 THEN 0
                            ELSE round((close_price - open_price) / open_price * 100, 4)
                       END,
                       points, 'rollup', now()
                FROM agg
                ON CONFLICT (pair, day) DO UPDATE
                SET open_price  = EXCLUDED.open_price,
                    high_price  = EXCLUDED.high_price,
                    low_price   = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    change_pct  = EXCLUDED.change_pct,
                    points      = EXCLUDED.points,
                    source      = EXCLUDED.source,
                    updated_at  = now()
                -- не вытесняем настоящий дневной диапазон одной нашей точкой
                WHERE EXCLUDED.high_price > EXCLUDED.low_price
                   OR daily_stats.high_price = daily_stats.low_price
                RETURNING 1
                """,
                tz_name,
                start,
                end,
            )
        return len(records)

    async def daily(
        self, pair: str, since: date, until: date | None = None
    ) -> list[tuple[date, float]]:
        if until is None:
            records = await self.pool.fetch(
                """
                SELECT day, close_price FROM daily_stats
                WHERE pair = $1 AND day >= $2
                ORDER BY day
                """,
                pair,
                since,
            )
        else:
            records = await self.pool.fetch(
                """
                SELECT day, close_price FROM daily_stats
                WHERE pair = $1 AND day >= $2 AND day <= $3
                ORDER BY day
                """,
                pair,
                since,
                until,
            )
        return [(record["day"], float(record["close_price"])) for record in records]

    async def upsert_daily(
        self,
        rows: Iterable[tuple[str, date, float, float, float, float, float, int, str]],
    ) -> int:
        """Строки: (pair, day, open, high, low, close, change_pct, points, source)."""
        prepared = [
            (
                row[0],
                row[1],
                _num(row[2]),
                _num(row[3]),
                _num(row[4]),
                _num(row[5]),
                Decimal(f"{row[6]:.4f}"),
                int(row[7]),
                row[8],
            )
            for row in rows
        ]
        if not prepared:
            return 0
        await self.pool.executemany(
            """
            INSERT INTO daily_stats (pair, day, open_price, high_price, low_price,
                                     close_price, change_pct, points, source, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
            ON CONFLICT (pair, day) DO UPDATE
            SET open_price  = EXCLUDED.open_price,
                high_price  = EXCLUDED.high_price,
                low_price   = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                change_pct  = EXCLUDED.change_pct,
                points      = EXCLUDED.points,
                source      = EXCLUDED.source,
                updated_at  = now()
            -- не вытесняем настоящий дневной диапазон вырожденной строкой
            WHERE EXCLUDED.high_price > EXCLUDED.low_price
               OR daily_stats.high_price = daily_stats.low_price
            """,
            prepared,
        )
        return len(prepared)

    # ------------------------------------------------------------------
    # Журнал и служебное
    # ------------------------------------------------------------------
    async def log_event(
        self, user_id: int, pair: str, period: str, compare_pair: str | None = None
    ) -> None:
        await self.pool.execute(
            """
            INSERT INTO chart_events (user_id, pair, period, compare_pair)
            VALUES ($1, $2, $3, $4)
            """,
            user_id,
            pair,
            period,
            compare_pair,
        )

    async def stats(self) -> dict[str, Any]:
        row = await self.pool.fetchrow(
            """
            SELECT (SELECT count(*) FROM rate_ticks)    AS ticks,
                   (SELECT count(*) FROM daily_stats)   AS days,
                   (SELECT count(*) FROM chart_events)  AS events,
                   (SELECT max(ts) FROM rate_ticks)     AS last_tick,
                   (SELECT max(day) FROM daily_stats)   AS last_day
            """
        )
        if row is None:
            return {}
        return dict(row)

    async def close(self) -> None:
        await self.pool.close()
