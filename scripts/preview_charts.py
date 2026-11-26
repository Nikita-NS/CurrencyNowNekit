"""Генерирует картинки для README из демо-данных (без сети и БД).

    python -m scripts.preview_charts
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from zoneinfo import ZoneInfo

from app.charts.menu import build_menu
from app.charts import render_png
from app.providers.demo import DemoProvider
from app.services.charts_service import ChartService
from app.services.rates import RateService

TZ = ZoneInfo("Europe/Moscow")
OUT = Path("docs")

SAMPLES = [
    ("USD", "1h", "chart-usd-1h"),
    ("RUB", "24h", "chart-rub-24h"),
    ("EUR", "7d", "chart-eur-7d"),
]


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    provider = DemoProvider(TZ)
    rates = RateService(None, provider, TZ, tz_name="Europe/Moscow")
    charts = ChartService(rates, TZ)

    for code, period, name in SAMPLES:
        bundle = await charts.single(code, period)
        (OUT / f"{name}.png").write_bytes(bundle.png)
        (OUT / f"{name}.svg").write_text(bundle.svg, encoding="utf-8")
        print(f"{name}.png  {len(bundle.png) // 1024} КБ")

    comparison = await charts.compare("EUR", "CNY", "1h")
    (OUT / "chart-compare.png").write_bytes(comparison.png)
    (OUT / "chart-compare.svg").write_text(comparison.svg, encoding="utf-8")
    print(f"chart-compare.png  {len(comparison.png) // 1024} КБ")

    (OUT / "menu.png").write_bytes(render_png(build_menu(await rates.menu_values())))
    print("menu.png")


if __name__ == "__main__":
    asyncio.run(main())
