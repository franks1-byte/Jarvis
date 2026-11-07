@echo off
title J.A.R.V.I.S. Launcher
cd /d "%~dp0"

if not exist "%~dp0config.json" (
  echo [X] Wala pa ma-extract ang folder.
  echo     Right-click sa Jarvis.zip ^> Extract All, dayon i-run ang Jarvis.bat sulod sa extracted folder.
  echo.
  pause
  exit /b 1
)

set "PY="
where py >nul 2>nul && set "PY=py" && set "PYW=pyw"
if not defined PY (
  python --version >nul 2>nul && set "PY=python" && set "PYW=pythonw"
)
if not defined PY (
  echo [X] Python wala makit-i.
  echo     I-install gikan sa https://www.python.org/downloads/ ug i-check ang "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

%PY% check_setup.py
if errorlevel 1 (
  echo.
  pause
  exit /b 1
)

echo Opening Jarvis...
start "" %PYW% gui.py %*
if exist jarvis_error.log del jarvis_error.log >nul 2>nul
timeout /t 2 >nul
