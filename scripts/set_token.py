"""Вставка токена бота в .env с проверкой через Telegram.

Запускается через set-token.cmd (двойным щелчком) или вручную:

    .venv\\Scripts\\python.exe -m scripts.set_token
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")

LINE = "=" * 62


def pause() -> None:
    try:
        input("\nНажмите Enter, чтобы закрыть окно...")
    except EOFError:
        pass


def write_token(token: str) -> None:
    """Меняет только строку BOT_TOKEN, остальные настройки сохраняет."""
    if ENV_PATH.is_file():
        keep = [
            line for line in ENV_PATH.read_text(encoding="utf-8").splitlines()
            if not line.startswith("BOT_TOKEN=")
        ]
    else:
        keep = [
            "# Настройки fxbot",
            "DATABASE_URL=postgresql://fxbot:fxbot@localhost:5432/fxbot",
            "RATES_PROVIDER=yahoo",
            "TZ_NAME=Europe/Moscow",
            "POLL_INTERVAL=60",
            "ADMIN_IDS=",
            "LOG_LEVEL=INFO",
        ]
    ENV_PATH.write_text(f"BOT_TOKEN={token}\n" + "\n".join(keep) + "\n", encoding="utf-8")


async def check(token: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url) as response:
                data = await response.json(content_type=None)
    except Exception as exc:  # noqa: BLE001 - сеть может быть недоступна
        return False, f"не удалось связаться с Telegram: {exc}"
    if data.get("ok"):
        user = data.get("result") or {}
        return True, f"@{user.get('username')} (имя: {user.get('first_name')})"
    return False, str(data.get("description") or data)


def main() -> int:
    print(LINE)
    print("  fxbot — вставка токена бота")
    print(LINE)
    print()
    print("Файл настроек:")
    print(f"  {ENV_PATH}")
    print()
    if ENV_PATH.is_file():
        current = [
            line for line in ENV_PATH.read_text(encoding="utf-8").splitlines()
            if line.startswith("BOT_TOKEN=")
        ]
        if current and current[0][len("BOT_TOKEN="):].strip():
            print("Сейчас в файле уже записан токен — новый заменит его.")
            print()
    print("Где взять токен:")
    print("  1. Откройте Telegram и найдите @BotFather")
    print("  2. Отправьте ему /newbot")
    print("  3. Придумайте имя и username (username должен кончаться на 'bot')")
    print("  4. BotFather пришлёт строку вида 1234567890:AAH...  — это и есть токен")
    print()
    print("Скопируйте её и вставьте сюда (правый клик в окне = вставка).")
    print()

    try:
        token = input("Токен: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nОтменено.")
        return 1

    # частая ошибка — скопировали вместе с лишним текстом
    token = token.strip().strip('"').strip("'")
    match = re.search(r"\d{6,}:[A-Za-z0-9_-]{30,}", token)
    if match:
        token = match.group(0)

    if not token:
        print("\n[ошибка] Токен пустой — ничего не записано.")
        return 1
    if not TOKEN_RE.match(token):
        print("\n[ошибка] Это не похоже на токен бота.")
        print("Ожидается примерно такой вид: 1234567890:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")
        print("Скопируйте строку у @BotFather целиком, без пробелов и кавычек.")
        return 1

    print("\nПроверяю токен в Telegram...")
    ok, info = asyncio.run(check(token))
    if not ok:
        print(f"[ошибка] Telegram отклонил токен: {info}")
        print("Проверьте, что скопировали его полностью. Ничего не записано.")
        return 1

    write_token(token)
    print(f"[готово] Токен верный: {info}")
    print(f"[готово] Записан в {ENV_PATH}")
    print()

    try:
        answer = input("Запустить бота сейчас? [Д/н]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "н"
    if answer in ("", "д", "да", "y", "yes"):
        return run_bot()

    print("Запустить позже можно двойным щелчком по run.cmd")
    print("В Telegram отправьте боту /start.")
    return 0


def run_bot() -> int:
    """Запускает run.py тем же интерпретатором (.venv)."""
    import subprocess

    print()
    print(LINE)
    print("  Бот запускается. Остановить — Ctrl+C в этом окне.")
    print("  Откройте Telegram и отправьте боту /start")
    print(LINE)
    print()
    try:
        return subprocess.call([sys.executable, str(ROOT / "run.py")])
    except KeyboardInterrupt:
        print("\nБот остановлен.")
        return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    code = main()
    pause()
    sys.exit(code)
