@echo off
title J.A.R.V.I.S. (debug)
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py"
echo Running Jarvis with the console visible. If it crashes, the error appears below.
echo.
%PY% gui.py
echo.
echo ===== Jarvis stopped. Kung naay error sa ibabaw, i-screenshot ug i-send. =====
pause
