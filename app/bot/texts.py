"""Тексты сообщений (HTML)."""

from __future__ import annotations

from ..charts.model import fmt_num
from ..formatting import arrow, plural, price_text, signed_pct
from ..pairs import get_pair
from ..services.charts_service import ChartBundle


def menu_caption() -> str:
    return (
        "<b>💱 Курсы валют</b>\n\n"
        "Выберите валюту — пришлю график за час.\n"
        "Рубль · Доллар · Евро · Юань \n"
        "Есть сравнение двух валют и SVG-файл.\n\n"
        "<i>Курсы снимаются раз в минуту, движения по дням хранятся в PostgreSQL.</i>"
    )


def single_caption(bundle: ChartBundle) -> str:
    values = [point.value for point in bundle.points]
    low, high = min(values), max(values)
    pair = bundle.pair
    count = len(bundle.points)
    return (
        f"<b>{pair.pair}</b> · {price_text(bundle.points[-1].value, pair.symbol)}\n"
        f"{arrow(bundle.change)} {fmt_num(abs(bundle.change), 2)} % {bundle.period.title}\n"
        f"Мин {price_text(low)} · Макс {price_text(high)}\n\n"
        f"<i>{bundle.source}</i>"
    )


def compare_caption(bundle: ChartBundle) -> str:
    pair_a, pair_b = bundle.pair, bundle.compare_pair
    assert pair_b is not None
    spread = bundle.change - bundle.compare_change
    total = len(bundle.points) + len(bundle.compare_points)
    return (
        f"<b>{pair_a.pair}</b> и <b>{pair_b.pair}</b>\n"
        f"Сравнение {bundle.period.title} в процентах\n\n"
        f"{pair_a.pair}: {signed_pct(bundle.change)}\n"
        f"{pair_b.pair}: {signed_pct(bundle.compare_change)}\n"
        f"Разрыв: {fmt_num(abs(spread), 2)} п.п.\n\n"
        f"<i>{bundle.source} · {total} {plural(total, 'точка', 'точки', 'точек')}</i>"
    )


def compare_first_caption() -> str:
    return "<b>📊 Сравнение валют</b>\n\nВыберите первую валюту."


def compare_second_caption(first_code: str) -> str:
    pair = get_pair(first_code)
    return (
        f"<b>📊 Сравнение валют</b>\n\n"
        f"Первая: {pair.flag} {pair.pair}\n"
        f"Теперь выберите вторую — построю оба графика в процентах."
    )


def svg_caption(bundle: ChartBundle) -> str:
    if bundle.compare_pair:
        title = f"{bundle.pair.pair} и {bundle.compare_pair.pair}"
    else:
        title = bundle.pair.pair
    return (
        f"<b>{title}</b> · {bundle.period.title}\n"
        "Векторный SVG: откройте файл в браузере — он масштабируется без потери качества."
    )


def hd_caption(bundle: ChartBundle) -> str:
    if bundle.compare_pair:
        title = f"{bundle.pair.pair} и {bundle.compare_pair.pair}"
    else:
        title = bundle.pair.pair
    return (
        f"<b>{title}</b> · {bundle.period.title}\n"
        "PNG 2560×1440 без сжатия — так картинка выглядит ровно так, как нарисована.\n"
        "<i>Telegram пережимает обычные фото в JPEG, поэтому текст на них мягче. "
        "Здесь сжатия нет: нажмите на файл, чтобы открыть в полном размере.</i>"
    )


def help_caption() -> str:
    return (
        "<b>Что умеет бот</b>\n\n"
        "/start — меню с курсами валют\n"
        "/rates — то же меню\n"
        "/stats — состояние базы (для админа)\n"
        "/id — ваш chat_id\n\n"
        "Нажмите валюту — получите график за час, 24 часа, 7 или 30 дней.\n"
        "Кнопка «Сравнить» строит два курса на одном графике в процентах.\n"
        "Кнопка «SVG-файл» присылает тот же график вектором."
    )


def error_caption(exc: Exception) -> str:
    text = str(exc)
    if not text:
        text = exc.__class__.__name__
    return f"⚠️ {text}"
