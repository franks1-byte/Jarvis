@echo off
title Restarting J.A.R.V.I.S.
cd /d "%~dp0"
echo Closing the old Jarvis...
powershell -NoProfile -Command "$ids = @(); $ids += Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '(gui|jarvis)\.py' -and $_.Name -match '(?i)^(py|python)' } | ForEach-Object { $_.ProcessId }; $ids += Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $_.OwningProcess }; $ids | Where-Object { $_ -and $_ -ne $PID } | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
timeout /t 2 >nul
echo Starting the new Jarvis...
call "%~dp0Jarvis.bat"
