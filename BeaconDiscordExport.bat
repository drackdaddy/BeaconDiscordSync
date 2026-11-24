@echo off
setlocal
cd /d "%~dp0"
title Beacon Discord export

rem ---- 1. Find Python (install it if missing) ----
call :findpython
if not defined PY (
    echo Python not found. Installing Python 3.13 with winget...
    where winget >nul 2>&1 || (
        echo winget is not available. Install Python from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH", then run this again.
        pause & exit /b 2
    )
    winget install -e --id Python.Python.3.13 --scope user --silent --accept-package-agreements --accept-source-agreements
    call :findpython
)
if not defined PY (
    echo Python was installed but could not be found. Close this window and run it again.
    pause & exit /b 2
)

rem ---- 2. Make sure discord.py and keyring are installed ----
%PY% -c "import discord, keyring" >nul 2>&1
if errorlevel 1 (
    echo Installing discord.py and keyring...
    %PY% -m pip install --user --upgrade discord.py keyring || (echo Could not install them. & pause & exit /b 2)
)

rem ---- 3. Ask for settings if needed, then export ----
echo.
%PY% beacon_discord_export.py
if errorlevel 1 (
    echo.
    echo Export failed - nothing was written or posted.
    pause & exit /b 2
)
echo.
pause
exit /b

:findpython
set "PY="
rem "py" launcher first, then python on PATH (skips the Microsoft Store stub), then the default install folder
py -3 -c "import sys" >nul 2>&1 && (set "PY=py -3" & exit /b)
python -c "import sys" >nul 2>&1 && (set "PY=python" & exit /b)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
exit /b
