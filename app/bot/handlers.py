"""Хендлеры: меню, графики, сравнение, SVG."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaPhoto, Message

from ..config import Settings
from ..db.repo import Repo
from ..providers.base import ProviderError
from ..services.charts_service import ChartBundle, ChartService
from . import keyboards as kb
from . import texts

log = logging.getLogger(__name__)
router = Router(name="charts")


# ---------------------------------------------------------------------------
# вспомогательные функции
# ---------------------------------------------------------------------------
async def _edit_photo(cb: CallbackQuery, png: bytes, caption: str, markup, settings: Settings) -> None:
    if settings.send_as == "document":
        # без сжатия Telegram: файл вместо фото
        await cb.message.answer_document(
            BufferedInputFile(png, "chart.png"), caption=caption, reply_markup=markup
        )
        return
    media = InputMediaPhoto(media=BufferedInputFile(png, filename="chart.png"), caption=caption)
    try:
        await cb.message.edit_media(media=media, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer_photo(BufferedInputFile(png, "chart.png"), caption=caption, reply_markup=markup)


async def _edit_text(cb: CallbackQuery, caption: str, markup) -> None:
    try:
        await cb.message.edit_caption(caption=caption, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer(caption, reply_markup=markup)


async def _send_menu(bot, chat_id: int, charts: ChartService) -> None:
    png = await charts.menu_card()
    await bot.send_photo(chat_id, BufferedInputFile(png, "menu.png"),
                         caption=texts.menu_caption(), reply_markup=kb.main_menu())


async def _log(repo: Repo | None, user_id: int, bundle: ChartBundle) -> None:
    if repo is None:
        return
    try:
        await repo.log_event(
            user_id,
            bundle.pair.pair,
            bundle.period.code,
            bundle.compare_pair.pair if bundle.compare_pair else None,
        )
    except Exception:  # noqa: BLE001 - журнал не должен ломать ответ
        log.exception("Не удалось записать событие в chart_events")


async def _fail(cb: CallbackQuery, exc: Exception) -> None:
    log.warning("Ошибка построения графика: %s", exc)
    try:
        await cb.answer(texts.error_caption(exc)[:190], show_alert=True)
    except TelegramBadRequest:
        pass


# ---------------------------------------------------------------------------
# команды
# ---------------------------------------------------------------------------
@router.message(CommandStart())
async def on_start(message: Message, charts: ChartService) -> None:
    await _send_menu(message.bot, message.chat.id, charts)


@router.message(Command("rates", "menu"))
async def on_menu(message: Message, charts: ChartService) -> None:
    await _send_menu(message.bot, message.chat.id, charts)


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(texts.help_caption())


@router.message(Command("id"))
async def on_id(message: Message) -> None:
    await message.answer(
        f"chat_id: <code>{message.chat.id}</code>\nuser_id: <code>{message.from_user.id}</code>"
    )


@router.message(Command("stats"))
async def on_stats(message: Message, repo: Repo | None, settings: Settings) -> None:
    if repo is None:
        await message.answer("PostgreSQL не подключён (DATABASE_URL пустой).")
        return
    if settings.admin_ids and message.from_user.id not in settings.admin_ids:
        await message.answer("Команда только для админа.")
        return
    data = await repo.stats()
    await message.answer(
        "<b>Состояние БД</b>\n"
        f"тиков курсов: <b>{data.get('ticks', 0)}</b>\n"
        f"дней в daily_stats: <b>{data.get('days', 0)}</b>\n"
        f"запросов графиков: <b>{data.get('events', 0)}</b>\n"
        f"последний тик: <code>{data.get('last_tick')}</code>\n"
        f"последний день: <code>{data.get('last_day')}</code>"
    )


# ---------------------------------------------------------------------------
# колбэки
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, charts: ChartService, settings: Settings) -> None:
    await cb.answer()
    png = await charts.menu_card()
    await _edit_photo(cb, png, texts.menu_caption(), kb.main_menu(), settings)


@router.callback_query(F.data.startswith("c:"))
async def cb_chart(
    cb: CallbackQuery, charts: ChartService, repo: Repo | None, settings: Settings
) -> None:
    _, code, period = cb.data.split(":")
    await cb.answer("Строю график…")
    await cb.bot.send_chat_action(cb.message.chat.id, "upload_photo")
    try:
        bundle = await charts.single(code, period)
    except (ProviderError, ValueError) as exc:
        await _fail(cb, exc)
        return
    png = bundle.hd_png if settings.send_as == "document" else bundle.png
    await _edit_photo(cb, png, texts.single_caption(bundle),
                      kb.chart_menu(code, period), settings)
    await _log(repo, cb.from_user.id, bundle)


@router.callback_query(F.data.startswith("svg:"))
async def cb_svg(cb: CallbackQuery, charts: ChartService) -> None:
    _, code, period = cb.data.split(":")
    await cb.answer("Готовлю SVG…")
    try:
        bundle = await charts.single(code, period)
    except (ProviderError, ValueError) as exc:
        await _fail(cb, exc)
        return
    await cb.message.answer_document(
        BufferedInputFile(bundle.svg.encode("utf-8"), filename=f"{bundle.filename}.svg"),
        caption=texts.svg_caption(bundle),
    )


@router.callback_query(F.data.startswith("hd:"))
async def cb_hd(cb: CallbackQuery, charts: ChartService) -> None:
    _, code, period = cb.data.split(":")
    await cb.answer("Готовлю PNG без сжатия…")
    try:
        bundle = await charts.single(code, period)
    except (ProviderError, ValueError) as exc:
        await _fail(cb, exc)
        return
    await cb.message.answer_document(
        BufferedInputFile(bundle.hd_png, filename=f"{bundle.filename}-2x.png"),
        caption=texts.hd_caption(bundle),
    )


@router.callback_query(F.data == "cmp")
async def cb_compare_start(cb: CallbackQuery) -> None:
    await cb.answer()
    await _edit_text(cb, texts.compare_first_caption(), kb.compare_picker(None))


@router.callback_query(F.data.startswith("cmp:"))
async def cb_compare_second(cb: CallbackQuery) -> None:
    _, first = cb.data.split(":")
    await cb.answer()
    await _edit_text(cb, texts.compare_second_caption(first), kb.compare_picker(first))


@router.callback_query(F.data.startswith("cmp2:"))
async def cb_compare(
    cb: CallbackQuery, charts: ChartService, repo: Repo | None, settings: Settings
) -> None:
    _, first, second, period = cb.data.split(":")
    await cb.answer("Сравниваю…")
    await cb.bot.send_chat_action(cb.message.chat.id, "upload_photo")
    try:
        bundle = await charts.compare(first, second, period)
    except (ProviderError, ValueError) as exc:
        await _fail(cb, exc)
        return
    png = bundle.hd_png if settings.send_as == "document" else bundle.png
    await _edit_photo(cb, png, texts.compare_caption(bundle),
                      kb.compare_chart(first, second, period), settings)
    await _log(repo, cb.from_user.id, bundle)


@router.callback_query(F.data.startswith("svgc:"))
async def cb_compare_svg(cb: CallbackQuery, charts: ChartService) -> None:
    _, first, second, period = cb.data.split(":")
    await cb.answer("Готовлю SVG…")
    try:
        bundle = await charts.compare(first, second, period)
    except (ProviderError, ValueError) as exc:
        await _fail(cb, exc)
        return
    await cb.message.answer_document(
        BufferedInputFile(bundle.svg.encode("utf-8"), filename=f"{bundle.filename}.svg"),
        caption=texts.svg_caption(bundle),
    )


@router.callback_query(F.data.startswith("hdc:"))
async def cb_compare_hd(cb: CallbackQuery, charts: ChartService) -> None:
    _, first, second, period = cb.data.split(":")
    await cb.answer("Готовлю PNG без сжатия…")
    try:
        bundle = await charts.compare(first, second, period)
    except (ProviderError, ValueError) as exc:
        await _fail(cb, exc)
        return
    await cb.message.answer_document(
        BufferedInputFile(bundle.hd_png, filename=f"{bundle.filename}-2x.png"),
        caption=texts.hd_caption(bundle),
    )
