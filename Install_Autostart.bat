@echo off
title Jarvis auto-start
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py"
%PY% install_startup.py
timeout /t 3 >nul
