# J.A.R.V.I.S. - Wake-on-LAN / Wake-on-Wi-Fi setup (run through Enable_Wake_On_LAN.bat as administrator)
$ErrorActionPreference = "SilentlyContinue"
$report = Join-Path $PSScriptRoot "wake_report.txt"
$log = New-Object System.Collections.Generic.List[string]
function Say($text, $color = "Gray") { Write-Host "  $text" -ForegroundColor $color; $log.Add($text) }

Write-Host ""
Write-Host "  J.A.R.V.I.S.  Wake setup" -ForegroundColor Cyan
Write-Host "  ------------------------" -ForegroundColor DarkCyan

# 1. Sleep type of this laptop
$states = (powercfg /a) -join "`n"
$modern = $states -match "S0 Low Power Idle"
if ($modern) { Say "SLEEP TYPE: Modern Standby (S0)" "Cyan" } else { Say "SLEEP TYPE: Classic sleep (S3)" "Cyan" }

# 2. Fast Startup off (needed for waking from Shutdown over Ethernet)
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" /v HiberbootEnabled /t REG_DWORD /d 0 /f | Out-Null
Say "[OK] Fast Startup turned off" "Green"

# 3. Modern Standby: keep Wi-Fi connected while asleep
if ($modern) {
    $sub = "fea3413e-7e05-4911-9a71-700331f1c294"; $set = "f15576e8-98b7-4186-b944-eafa664402d9"
    powercfg /setacvalueindex SCHEME_CURRENT $sub $set 1 | Out-Null
    powercfg /setdcvalueindex SCHEME_CURRENT $sub $set 1 | Out-Null
    powercfg /setactive SCHEME_CURRENT | Out-Null
    Say "[OK] Wi-Fi stays connected during sleep" "Green"
}

# 4. Let every physical adapter wake the laptop with a magic packet
$ethernet = $null; $wifi = $null
foreach ($a in (Get-NetAdapter -Physical)) {
    Set-NetAdapterPowerManagement -Name $a.Name -WakeOnMagicPacket Enabled
    Set-NetAdapterPowerManagement -Name $a.Name -AllowComputerToTurnOffDevice Disabled
    foreach ($p in (Get-NetAdapterAdvancedProperty -Name $a.Name)) {
        if ($p.DisplayName -match "(?i)magic packet|wake on lan|wake-on-lan|shutdown wake|wol|wowlan|wake on wlan") {
            foreach ($v in @("Enabled", "On")) {
                if ($p.ValidDisplayValues -contains $v) {
                    Set-NetAdapterAdvancedProperty -Name $a.Name -DisplayName $p.DisplayName -DisplayValue $v; break
                }
            }
        }
    }
    powercfg /deviceenablewake "$($a.InterfaceDescription)" 2>$null | Out-Null
    $pm = Get-NetAdapterPowerManagement -Name $a.Name
    $isWifi = ($a.MediaType -match "802.11") -or ($a.Name -match "(?i)wi-?fi|wlan|wireless")
    if ($isWifi -and -not $wifi) { $wifi = $a } elseif (-not $isWifi -and -not $ethernet) { $ethernet = $a }
    $kind = if ($isWifi) { "WI-FI" } else { "ETHERNET" }
    Say ("ADAPTER {0}: {1} | MAC {2} | magic packet {3} | status {4}" -f $kind, $a.InterfaceDescription, ($a.MacAddress -replace "-", ":"), $pm.WakeOnMagicPacket, $a.Status) "Green"
}

# 5. Address the iPhone needs
$main = if ($wifi) { $wifi } else { $ethernet }
if ($main) {
    $ip = Get-NetIPAddress -InterfaceIndex $main.ifIndex -AddressFamily IPv4 | Select-Object -First 1
    if ($ip) {
        $bytes = ([System.Net.IPAddress]$ip.IPAddress).GetAddressBytes()
        $mask = [uint32]([math]::Pow(2, 32) - [math]::Pow(2, 32 - $ip.PrefixLength))
        $mb = [BitConverter]::GetBytes($mask); [Array]::Reverse($mb)
        $bc = for ($i = 0; $i -lt 4; $i++) { $bytes[$i] -bor (255 -bxor $mb[$i]) }
        Say ("IP {0} | BROADCAST {1}" -f $ip.IPAddress, ($bc -join ".")) "Cyan"
    }
    Say ("USE THIS MAC IN THE IPHONE APP: {0}" -f ($main.MacAddress -replace "-", ":")) "Cyan"
}
$wow = (netsh wlan show wirelesscapabilities) | Select-String -Pattern "(?i)wake|wow"
foreach ($l in $wow) { Say ("WLAN: " + $l.Line.Trim()) }
$armed = (powercfg /devicequery wake_armed) -join " | "
Say ("WAKE ARMED: " + $armed)
Say "POWER STATES:"; foreach ($l in (powercfg /a)) { if ($l.Trim()) { $log.Add("   " + $l.Trim()) } }

$log | Set-Content -Path $report -Encoding UTF8
Write-Host ""
Write-Host "  Done. Report saved to wake_report.txt" -ForegroundColor Cyan
Write-Host "  If waking still fails: enable 'Wake on LAN' / 'Wake on WLAN' in the BIOS (F2/F10/Del at boot)." -ForegroundColor White
Write-Host ""
