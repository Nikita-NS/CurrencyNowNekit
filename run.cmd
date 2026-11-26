@echo off
rem Launch fxbot using the Python from .venv (no PowerShell policy involved).
rem Usage: run.cmd   (double-click also works)
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\python.exe" (
    echo [fxbot] .venv not found.
    echo [fxbot] Create it:  "D:\Python 3.11\python.exe" -m venv .venv
    echo [fxbot] Then:       .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [fxbot] Starting. Keep this window open - the bot works only while it runs.
echo [fxbot] To stop: press Ctrl+C or close this window.
echo.

".venv\Scripts\python.exe" run.py %*
set EXITCODE=%ERRORLEVEL%

echo.
if not "%EXITCODE%"=="0" (
    echo [fxbot] Bot stopped with error code %EXITCODE%. Read the message above.
) else (
    echo [fxbot] Bot finished normally.
)
echo.
pause
exit /b %EXITCODE%
