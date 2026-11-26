-- Схема БД fxbot. Скрипт идемпотентный: его можно запускать на каждом старте.
-- Применяется автоматически (app/db/migrate.py) или вручную: psql -f schema.sql

-- Сырые точки курсов, которые снимает поллер (одна в минуту на пару).
CREATE TABLE IF NOT EXISTS rate_ticks (
    id      BIGSERIAL      PRIMARY KEY,
    pair    TEXT           NOT NULL,
    ts      TIMESTAMPTZ    NOT NULL,
    price   NUMERIC(18, 8) NOT NULL,
    source  TEXT           NOT NULL DEFAULT 'poll',
    CONSTRAINT rate_ticks_pair_ts_uniq UNIQUE (pair, ts)
);

CREATE INDEX IF NOT EXISTS rate_ticks_pair_ts_idx ON rate_ticks (pair, ts DESC);
CREATE INDEX IF NOT EXISTS rate_ticks_ts_idx ON rate_ticks (ts DESC);

-- Дневная агрегация: движение курса по дням (open/high/low/close + %).
CREATE TABLE IF NOT EXISTS daily_stats (
    pair        TEXT           NOT NULL,
    day         DATE           NOT NULL,
    open_price  NUMERIC(18, 8) NOT NULL,
    high_price  NUMERIC(18, 8) NOT NULL,
    low_price   NUMERIC(18, 8) NOT NULL,
    close_price NUMERIC(18, 8) NOT NULL,
    change_pct  NUMERIC(10, 4) NOT NULL DEFAULT 0,
    points      INTEGER        NOT NULL DEFAULT 0,
    source      TEXT           NOT NULL DEFAULT 'rollup',
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT now(),
    PRIMARY KEY (pair, day)
);

CREATE INDEX IF NOT EXISTS daily_stats_day_idx ON daily_stats (day DESC);

-- Журнал: кто какие графики запрашивал (пригодится для аналитики).
CREATE TABLE IF NOT EXISTS chart_events (
    id           BIGSERIAL   PRIMARY KEY,
    user_id      BIGINT      NOT NULL,
    pair         TEXT        NOT NULL,
    period       TEXT        NOT NULL,
    compare_pair TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chart_events_created_idx ON chart_events (created_at DESC);
