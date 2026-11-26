@echo off
rem Prompts for the bot token and writes it into .env (Russian UI in Python).
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\python.exe" (
    echo [fxbot] .venv not found. Run the setup first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" scripts\set_token.py
exit /b %ERRORLEVEL%
