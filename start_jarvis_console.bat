@echo off
title J.A.R.V.I.S. (console)
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py"
%PY% check_setup.py
if errorlevel 1 (pause & exit /b 1)
%PY% jarvis.py
pause
