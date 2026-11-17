@echo off
title Restarting J.A.R.V.I.S.
cd /d "%~dp0"
echo Closing the old Jarvis...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(pythonw?3?|pyw?)\.exe$' -and $_.CommandLine -match '(gui|jarvis)\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
timeout /t 2 >nul
echo Starting the new Jarvis...
call "%~dp0Jarvis.bat"
