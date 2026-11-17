# J.A.R.V.I.S. - Wi-Fi wake fix + diagnostics (run through Wake_Fix.bat as administrator)
$ErrorActionPreference = "SilentlyContinue"
$out = Join-Path $PSScriptRoot "wake_report2.txt"
$L = New-Object System.Collections.Generic.List[string]
function Add($t) { $L.Add([string]$t); Write-Host $t }

Add "== WAKE PROGRAMMABLE DEVICES =="
$prog = powercfg /devicequery wake_programmable
foreach ($d in $prog) { if ($d.Trim()) { Add "  $d" } }
Add "== WAKE ARMED (before) =="
foreach ($d in (powercfg /devicequery wake_armed)) { if ($d.Trim()) { Add "  $d" } }

$wifi = Get-NetAdapter -Physical | Where-Object { $_.MediaType -match "802.11" -or $_.Name -match "(?i)wi-?fi" } | Select-Object -First 1
$pnp = Get-PnpDevice -InstanceId $wifi.PnPDeviceID
Add ("WIFI: {0} | {1} | driver {2} ({3})" -f $wifi.Name, $wifi.InterfaceDescription, $wifi.DriverVersion, $wifi.DriverDate)
Add ("PNP NAME: {0}" -f $pnp.FriendlyName)

# Arm the Wi-Fi card to wake the PC (same as Device Manager > Power Management > Allow this device to wake the computer)
$names = @($pnp.FriendlyName, $wifi.InterfaceDescription) + @($prog | Where-Object { $_ -match "(?i)wi-?fi|wireless|wlan|mediatek|rz616|mt79" })
foreach ($n in ($names | Where-Object { $_ } | Select-Object -Unique)) {
    $r = (powercfg /deviceenablewake "$n" 2>&1) -join " "
    Add ("ENABLEWAKE '{0}' -> {1}" -f $n, $(if ($r) { $r } else { "ok" }))
}
Set-NetAdapterPowerManagement -Name $wifi.Name -WakeOnMagicPacket Enabled -WakeOnPattern Enabled

Add "== WAKE ARMED (after) =="
foreach ($d in (powercfg /devicequery wake_armed)) { if ($d.Trim()) { Add "  $d" } }

Add "== ADAPTER POWER MANAGEMENT =="
(Get-NetAdapterPowerManagement -Name $wifi.Name | Format-List * | Out-String -Width 220) -split "`n" | Where-Object { $_.Trim() } | ForEach-Object { Add "  $($_.Trim())" }
Add "== ADAPTER ADVANCED PROPERTIES =="
foreach ($p in (Get-NetAdapterAdvancedProperty -Name $wifi.Name)) {
    Add ("  {0} = {1}   [{2}]" -f $p.DisplayName, $p.DisplayValue, ($p.ValidDisplayValues -join ", "))
}
Add "== LAST WAKE =="
foreach ($d in (powercfg /lastwake)) { if ($d.Trim()) { Add "  $d" } }
Add "== RECENT STANDBY EVENTS (506 enter / 507 exit) =="
Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-Kernel-Power'; Id = 506, 507 } -MaxEvents 8 |
    ForEach-Object { Add ("  {0} [{1}] {2}" -f $_.TimeCreated, $_.Id, ($_.Message -replace "\s+", " ")) }
Add "== NETWORK IN STANDBY SETTING =="
foreach ($d in (powercfg /q SCHEME_CURRENT fea3413e-7e05-4911-9a71-700331f1c294 f15576e8-98b7-4186-b944-eafa664402d9)) { if ($d.Trim()) { Add "  $($d.Trim())" } }
Add "== POWER SOURCE =="
$b = Get-CimInstance Win32_Battery | Select-Object -First 1
Add ("  BatteryStatus={0} (2 = plugged in) Charge={1}%" -f $b.BatteryStatus, $b.EstimatedChargeRemaining)

$L | Set-Content -Path $out -Encoding UTF8
Write-Host ""
Write-Host "  Done. Saved wake_report2.txt" -ForegroundColor Cyan
