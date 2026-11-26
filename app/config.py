"""Окружение и настройки (читаются из .env / переменных окружения)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigError(RuntimeError):
    pass


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv необязателен
        return
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is not None:
        value = value.strip()
    return value


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} должен быть числом, получено: {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str = ""
    rates_provider: str = "yahoo"
    tz_name: str = "Europe/Moscow"
    poll_interval: int = 60
    admin_ids: tuple[int, ...] = ()
    log_level: str = "INFO"
    #: "photo" — график приходит картинкой в чат (Telegram жмёт в JPEG),
    #: "document" — файлом без сжатия (качество 1:1, но превью меньше)
    send_as: str = "photo"

    @property
    def db_enabled(self) -> bool:
        return bool(self.database_url)

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.tz_name)
        except ZoneInfoNotFoundError as exc:
            raise ConfigError(
                f"Не найден часовой пояс {self.tz_name!r}. "
                "На Windows помогает `pip install tzdata`; проверьте написание зоны."
            ) from exc

    @classmethod
    def load(cls) -> "Settings":
        _load_dotenv()
        token = _env("BOT_TOKEN") or ""
        if not token:
            raise ConfigError(
                "Не задан BOT_TOKEN. Скопируйте .env.example в .env и вставьте токен от @BotFather."
            )
        admins: list[int] = []
        for chunk in (_env("ADMIN_IDS") or "").replace(";", ",").split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                admins.append(int(chunk))
        return cls(
            bot_token=token,
            database_url=_env("DATABASE_URL") or "",
            rates_provider=(_env("RATES_PROVIDER") or "yahoo").lower(),
            tz_name=_env("TZ_NAME") or "Europe/Moscow",
            poll_interval=max(20, _env_int("POLL_INTERVAL", 60)),
            admin_ids=tuple(admins),
            log_level=(_env("LOG_LEVEL") or "INFO").upper(),
            send_as=(_env("SEND_AS") or "photo").lower(),
        )
