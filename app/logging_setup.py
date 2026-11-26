"""Логирование: консоль + файл с ротацией.

Файл нужен для запуска без окна консоли (Планировщик задач, служба Windows):
там stdout отсутствует, и без файла сообщения бота пропадают.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "fxbot.log"

FORMAT = "%(asctime)s %(levelname)-7s %(name)-24s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


def _console_handler() -> logging.Handler | None:
    """Консольный лог. При запуске через pythonw.exe потока вывода нет."""
    stream = sys.stdout or sys.stderr
    if stream is None:
        return None
    try:
        stream.write("")
    except Exception:  # noqa: BLE001 - поток может быть закрыт или недоступен
        return None
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)-24s %(message)s", "%H:%M:%S"))
    return handler


def _file_handler(level: int) -> logging.Handler | None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(FORMAT, DATEFMT))
        handler.setLevel(level)
        return handler
    except OSError:
        return None


def setup_logging(level: str = "INFO") -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(numeric)

    console = _console_handler()
    if console is not None:
        root.addHandler(console)

    file_handler = _file_handler(numeric)
    if file_handler is not None:
        root.addHandler(file_handler)

    # aiogram пишет очень много служебного
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
