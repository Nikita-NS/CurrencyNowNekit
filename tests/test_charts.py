"""Тесты движка графиков, провайдеров и форматирования.

Запуск:  python -m unittest discover -s tests -t .
Не требуют ни сети, ни aiogram, ни PostgreSQL.
"""

from __future__ import annotations

import asyncio
import json
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.charts import ChartSpec, Point, SeriesInput, build_layout, render_png, render_svg
from app.charts.menu import CARD_H, CARD_W, build_menu
from app.charts.model import (
    PLOT_BOTTOM,
    PLOT_LEFT,
    PLOT_RIGHT,
    PLOT_TOP,
    decimals_for_step,
    fmt_num,
    fmt_pct,
    nice_ticks,
)
from app.formatting import change_text, percent_change, price_text, signed_pct
from app.pairs import PAIRS, PAIR_ORDER, PERIODS
from app.providers.demo import DemoProvider, value_at
from app.providers.base import Bar
from app.providers.yahoo_parse import (
    aggregate_bars_daily,
    aggregate_daily,
    derive_series,
    invert_bars,
    parse_bars,
    parse_chart,
)

MSK = ZoneInfo("Europe/Moscow")
FIXTURES = Path(__file__).parent / "fixtures"


def make_points(count: int = 60, base: float = 82.0, start: datetime | None = None) -> list[Point]:
    start = start or datetime.now(MSK).replace(second=0, microsecond=0) - timedelta(minutes=count - 1)
    points = []
    value = base
    for index in range(count):
        value += ((index * 37) % 11 - 5) / 1000
        points.append(Point(start + timedelta(minutes=index), round(value, 4)))
    return points


class YahooParseTest(unittest.TestCase):
    def test_fixture_is_parsed_and_nulls_dropped(self) -> None:
        payload = json.loads((FIXTURES / "yahoo_usdrub_1h.json").read_text(encoding="utf-8"))
        points, price = parse_chart(payload)

        self.assertEqual(len(points), 11)          # 12 баров, один с null
        self.assertAlmostEqual(price or 0, 82.186, places=3)
        self.assertEqual(points, sorted(points, key=lambda p: p.ts))
        self.assertTrue(all(p.value > 0 for p in points))

    def test_broken_payload(self) -> None:
        self.assertEqual(parse_chart({}), ([], None))
        self.assertEqual(parse_chart({"chart": {"result": []}}), ([], None))

    def test_invert(self) -> None:
        points = [Point(datetime(2026, 1, 1, tzinfo=MSK), 82.0),
                  Point(datetime(2026, 1, 1, 1, tzinfo=MSK), 100.0)]
        inverted = derive_series(points, [], "invert")
        self.assertAlmostEqual(inverted[0].value, 1 / 82.0)
        self.assertAlmostEqual(inverted[1].value, 0.01)

    def test_multiply_and_divide(self) -> None:
        left = [Point(datetime(2026, 1, 1, tzinfo=MSK), 2.0)]
        right = [Point(datetime(2026, 1, 1, tzinfo=MSK), 3.0)]
        self.assertAlmostEqual(derive_series(left, right, "*")[0].value, 6.0)
        self.assertAlmostEqual(derive_series(left, right, "/")[0].value, 2 / 3)

    def test_derive_ignores_non_matching_timestamps(self) -> None:
        left = [Point(datetime(2026, 1, 1, tzinfo=MSK), 2.0)]
        right = [Point(datetime(2026, 1, 1, 5, tzinfo=MSK), 3.0)]
        self.assertEqual(derive_series(left, right, "*"), [])


class AggregateDailyTest(unittest.TestCase):
    """Свёртка часового ряда в дневной — запасной путь для пар без дневных свечей."""

    def test_one_point_per_day_with_last_close(self) -> None:
        base = datetime(2026, 3, 1, tzinfo=MSK)
        points = [
            Point(base.replace(hour=10), 82.0),
            Point(base.replace(hour=18), 82.5),
            Point(base.replace(hour=23, minute=30), 82.9),   # close дня
            Point(base.replace(hour=23, minute=59) + timedelta(days=1), 83.4),
        ]
        daily = aggregate_daily(points, MSK)
        self.assertEqual(len(daily), 2)
        self.assertAlmostEqual(daily[0].value, 82.9)
        self.assertAlmostEqual(daily[1].value, 83.4)
        self.assertEqual(daily[0].ts.date(), base.date())

    def test_days_follow_timezone(self) -> None:
        # 21:30 UTC = 00:30 следующего дня по Москве — попадёт в следующий день
        moment = datetime(2026, 3, 1, 21, 30, tzinfo=timezone.utc)
        daily = aggregate_daily([Point(moment, 82.0)], MSK)
        self.assertEqual(daily[0].ts.date(), datetime(2026, 3, 2).date())

    def test_empty(self) -> None:
        self.assertEqual(aggregate_daily([], MSK), [])


class ParseBarsTest(unittest.TestCase):
    """Свечи: без open/high/low в daily_stats не будет дневного движения."""

    def _payload(self) -> dict:
        base = int(datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp())
        return {
            "chart": {
                "result": [
                    {
                        "timestamp": [base, base + 86400, base + 2 * 86400],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [82.0, 82.5, None],
                                    "high": [82.9, 83.1, None],
                                    "low": [81.8, 82.2, None],
                                    "close": [82.5, 82.7, None],
                                }
                            ]
                        },
                    }
                ]
            }
        }

    def test_bars_keep_full_range(self) -> None:
        bars = parse_bars(self._payload())
        self.assertEqual(len(bars), 2)          # третий бар без close пропущен
        first = bars[0]
        self.assertAlmostEqual(first.open, 82.0)
        self.assertAlmostEqual(first.high, 82.9)
        self.assertAlmostEqual(first.low, 81.8)
        self.assertAlmostEqual(first.close, 82.5)
        self.assertTrue(first.has_range)
        self.assertAlmostEqual(first.change_pct, (82.5 / 82.0 - 1) * 100, places=6)

    def test_missing_ohlc_falls_back_to_close(self) -> None:
        payload = self._payload()
        payload["chart"]["result"][0]["indicators"]["quote"][0]["high"] = [None, None, None]
        bars = parse_bars(payload)
        self.assertAlmostEqual(bars[0].high, 82.5)

    def test_broken_payload(self) -> None:
        self.assertEqual(parse_bars({}), [])
        self.assertEqual(parse_bars({"chart": {"result": []}}), [])

    def test_invert_swaps_open_and_close(self) -> None:
        bar = Bar(datetime(2026, 3, 1, tzinfo=MSK), open=80.0, high=84.0, low=76.0, close=82.0)
        inverted = invert_bars([bar])[0]
        self.assertAlmostEqual(inverted.open, 1 / 82.0)
        self.assertAlmostEqual(inverted.close, 1 / 80.0)
        self.assertAlmostEqual(inverted.high, 1 / 76.0)   # максимум обратной пары
        self.assertAlmostEqual(inverted.low, 1 / 84.0)

    def test_aggregate_bars_into_days(self) -> None:
        base = datetime(2026, 3, 2, 10, tzinfo=MSK)
        hours = [
            Bar(base, open=82.0, high=82.2, low=81.9, close=82.1),
            Bar(base.replace(hour=15), open=82.1, high=82.8, low=82.0, close=82.6),
            Bar(base.replace(hour=23), open=82.6, high=82.7, low=82.3, close=82.4),
        ]
        daily = aggregate_bars_daily(hours, MSK)
        self.assertEqual(len(daily), 1)
        self.assertAlmostEqual(daily[0].open, 82.0)    # open первого часа
        self.assertAlmostEqual(daily[0].close, 82.4)   # close последнего часа
        self.assertAlmostEqual(daily[0].high, 82.8)    # максимум за день
        self.assertAlmostEqual(daily[0].low, 81.9)     # минимум за день


class YahooProviderSessionTest(unittest.IsolatedAsyncioTestCase):
    """start() зовут конкурентно при прогреве — сессия должна быть одна."""

    async def test_concurrent_start_creates_single_session(self) -> None:
        from app.providers.yahoo import YahooProvider

        provider = YahooProvider(tz=MSK)
        try:
            await asyncio.gather(*(provider.start() for _ in range(5)))
            sessions = {id(provider._session)}
            self.assertEqual(len(sessions), 1)
            self.assertIsNotNone(provider._session)
            self.assertFalse(provider._session.closed)
        finally:
            await provider.close()
        self.assertIsNone(provider._session)


class TicksTest(unittest.TestCase):
    def test_nice_ticks_cover_range(self) -> None:
        ticks = nice_ticks(81.93, 82.47)
        self.assertGreaterEqual(len(ticks), 3)
        self.assertLessEqual(len(ticks), 10)
        self.assertLessEqual(ticks[0], 82.0)
        self.assertGreaterEqual(ticks[-1], 82.4)
        self.assertEqual(ticks, sorted(ticks))

    def test_decimals(self) -> None:
        self.assertEqual(decimals_for_step(0.1), 1)
        self.assertEqual(decimals_for_step(0.25), 2)
        self.assertEqual(decimals_for_step(0.05), 2)
        self.assertEqual(decimals_for_step(0.002), 3)
        self.assertEqual(decimals_for_step(1.0), 0)

    def test_number_format_ru(self) -> None:
        self.assertEqual(fmt_num(82.19, 2).replace("\u00a0", " "), "82,19")
        self.assertEqual(fmt_pct(-0.42).replace("\u00a0", " "), "\u22120,42 %")


class LayoutTest(unittest.TestCase):
    def _spec(self, points: list[Point]) -> ChartSpec:
        return ChartSpec(
            title="USD/RUB",
            subtitle="Доллар США · ₽ за 1 $ · за час",
            footer="Данные: тест",
            series=[SeriesInput("USD/RUB", "Доллар", "#5B9DFF", tuple(points))],
            badge="USD",
            value_text="82,00 ₽",
            delta_text="▲ 0,10 %",
            delta_kind="up",
        )

    def test_points_stay_inside_plot(self) -> None:
        points = make_points(60)
        layout = build_layout(self._spec(points), 3600, 900, MSK)
        main_lines = [p for p in layout.polylines if p.width > 3]
        self.assertTrue(main_lines)
        for x, y in main_lines[0].points:
            self.assertGreaterEqual(x, PLOT_LEFT)
            self.assertLessEqual(x, PLOT_RIGHT)
            self.assertGreaterEqual(y, PLOT_TOP - 1)
            self.assertLessEqual(y, PLOT_BOTTOM + 1)

    def test_layout_has_grid_and_axes(self) -> None:
        layout = build_layout(self._spec(make_points(30)), 3600, 900, MSK)
        texts = " ".join(t.text for t in layout.texts)
        self.assertIn("USD/RUB", texts)
        self.assertIn("82,00", texts)
        # подписи осей: минимум 5 по Y и хотя бы одна по X, все одного кегля
        axis_labels = [t for t in layout.texts if t.size == 18]
        self.assertGreaterEqual(len(axis_labels), 5)

    def test_percent_mode_legend(self) -> None:
        now = datetime.now(MSK).replace(second=0, microsecond=0)
        flat = [Point(now - timedelta(minutes=10 - i), 90.25) for i in range(10)]
        rising = [Point(now - timedelta(minutes=10 - i), 12.3 * (1 + i * 0.001)) for i in range(10)]
        spec = ChartSpec(
            title="EUR/RUB и CNY/RUB",
            subtitle="Сравнение",
            footer="тест",
            series=[
                SeriesInput("EUR/RUB", "Евро", "#B18CFF", tuple(flat)),
                SeriesInput("CNY/RUB", "Юань", "#FFB547", tuple(rising)),
            ],
            mode="percent",
        )
        layout = build_layout(spec, 900, 300, MSK)
        texts = " ".join(t.text for t in layout.texts)
        self.assertIn("0,00", texts)
        self.assertIn("CNY/RUB", texts)

    def test_sparse_window_falls_back_to_data(self) -> None:
        old = datetime.now(MSK) - timedelta(days=3)
        points = [Point(old + timedelta(minutes=10 * i), 82.0 + i * 0.01) for i in range(5)]
        layout = build_layout(self._spec(points), 3600, 900, MSK)
        self.assertGreaterEqual(len(layout.polylines), 1)
        coords = layout.polylines[0].points
        for x, y in coords:
            self.assertGreaterEqual(x, PLOT_LEFT)
            self.assertLessEqual(x, PLOT_RIGHT)


class RenderTest(unittest.TestCase):
    def test_png_signature(self) -> None:
        layout = build_layout(
            ChartSpec(
                title="USD/RUB",
                subtitle="тест",
                footer="тест",
                series=[SeriesInput("USD/RUB", "Доллар", "#5B9DFF", tuple(make_points(40)))],
            ),
            3600, 900, MSK,
        )
        payload = render_png(layout)
        self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(payload), 20_000)
        self.assertEqual(layout.width, 1280)
        self.assertEqual(layout.height, 720)

    def test_svg_is_valid_xml(self) -> None:
        layout = build_layout(
            ChartSpec(
                title="EUR/RUB",
                subtitle="тест & <проверка>",
                footer="тест",
                series=[SeriesInput("EUR/RUB", "Евро", "#B18CFF", tuple(make_points(20, 90.0)))],
                value_text="90,25 ₽",
            ),
            3600, 900, MSK,
        )
        svg = render_svg(layout)
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn('width="1280"', svg)
        self.assertNotIn("None", svg)
        self.assertIn("90,25", svg)

    def test_menu_card(self) -> None:
        values = {"USD": (82.19, -0.42), "EUR": (90.25, 0.12), "CNY": (12.33, 0.03), "RUB": (0.0122, 0.4)}
        layout = build_menu(values)
        self.assertEqual((layout.width, layout.height), (CARD_W, CARD_H))
        payload = render_png(layout)
        self.assertTrue(payload.startswith(b"\x89PNG"))
        texts = " ".join(t.text for t in layout.texts)
        for pair in PAIRS.values():
            self.assertIn(pair.title, texts)


class FormattingTest(unittest.TestCase):
    def test_price_text(self) -> None:
        self.assertEqual(price_text(82.186).replace("\u00a0", " "), "82,19")
        self.assertEqual(price_text(0.012173, "$").replace("\u00a0", " "), "0,01217 $")

    def test_change_text(self) -> None:
        self.assertTrue(change_text(-0.42).startswith("▼"))
        self.assertTrue(change_text(0.42).startswith("▲"))
        self.assertTrue(change_text(0).startswith("•"))
        self.assertEqual(signed_pct(1.5).replace("\u00a0", " "), "+1,50 %")

    def test_percent_change(self) -> None:
        self.assertAlmostEqual(percent_change(100, 110), 10.0)
        self.assertAlmostEqual(percent_change(0, 110), 0.0)


class DemoProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_history_shape(self) -> None:
        provider = DemoProvider(MSK)
        points = await provider.history(PAIRS["USD"], PERIODS["1h"])
        self.assertGreaterEqual(len(points), 30)
        self.assertEqual(points, sorted(points, key=lambda p: p.ts))
        self.assertTrue(all(70 < p.value < 100 for p in points))

    async def test_value_is_stable_for_same_minute(self) -> None:
        moment = datetime(2026, 11, 26, 12, 0, 30, tzinfo=MSK)
        self.assertEqual(value_at("USD/RUB", moment), value_at("USD/RUB", moment))
        self.assertNotEqual(value_at("USD/RUB", moment), value_at("EUR/RUB", moment))

    async def test_all_pairs_have_data(self) -> None:
        provider = DemoProvider(MSK)
        for code in PAIR_ORDER:
            price = await provider.latest(PAIRS[code])
            self.assertGreater(price, 0)


if __name__ == "__main__":
    unittest.main()
