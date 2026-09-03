@echo off
REM Double-click me (or run from a terminal) to rebuild dist\spellbook.exe.
REM Passes any extra args through, e.g.:  build.bat --clean --run
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

"%PYTHON%" build.py %*
set "RC=%ERRORLEVEL%"

REM Keep the window open when launched by double-click so output stays visible.
echo.
pause
exit /b %RC%
