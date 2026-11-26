"""Проброс сервисов в хендлеры (DI через data middleware)."""

from __future__ import annotations

from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class ServicesMiddleware(BaseMiddleware):
    def __init__(self, **services: Any) -> None:
        self.services = services

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        data.update(self.services)
        return await handler(event, data)
