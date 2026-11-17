@echo off
title J.A.R.V.I.S. Wi-Fi wake fix
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0wake_fix.ps1"
timeout /t 8
