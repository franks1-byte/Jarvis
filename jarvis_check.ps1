# Jarvis health check: is it running, reachable, allowed through the firewall, and set to auto-start?
$ErrorActionPreference = "SilentlyContinue"
$out = Join-Path $PSScriptRoot "jarvis_check.txt"
$L = New-Object System.Collections.Generic.List[string]
function Add($t) { $L.Add([string]$t) }
$cfg = Get-Content (Join-Path $PSScriptRoot "config.json") -Raw | ConvertFrom-Json
$tok = $cfg.remote.token; $port = $cfg.remote.port
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '(gui|jarvis)\.py' }
Add ("JARVIS PROCESSES: " + ($procs | ForEach-Object { "$($_.Name) pid=$($_.ProcessId) started=$($_.CreationDate)" }) -join " ; ")
foreach ($h in @("127.0.0.1", "192.168.0.25")) {
  try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://${h}:$port/api/status?t=$tok"; Add "STATUS ${h}: $($r.StatusCode) $($r.Content)" }
  catch { Add "STATUS ${h}: FAILED $($_.Exception.Message)" }
}
try { $p = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$port/?t=$tok"; Add ("PANEL HAS TURN ON BUTTON: " + ($p.Content -match 'data-act="wake"')) } catch { Add "PANEL: FAILED" }
Get-NetConnectionProfile | ForEach-Object { Add "NETWORK: $($_.Name) category=$($_.NetworkCategory) iface=$($_.InterfaceAlias)" }
Get-NetFirewallRule -Direction Inbound | Where-Object { $_.DisplayName -match 'python' } | ForEach-Object {
  Add "FIREWALL: $($_.DisplayName) action=$($_.Action) enabled=$($_.Enabled) profile=$($_.Profile)" }
$vbs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.vbs"
Add ("AUTOSTART: " + (Test-Path $vbs))
Add ("IPV4: " + ((Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -match 'Wi-Fi' }).IPAddress -join ","))
$L | Set-Content -Path $out -Encoding UTF8
