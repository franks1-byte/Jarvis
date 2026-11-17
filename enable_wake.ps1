# J.A.R.V.I.S. - Wake-on-LAN setup (run through Enable_Wake_On_LAN.bat as administrator)
$ErrorActionPreference = "SilentlyContinue"
Write-Host ""
Write-Host "  J.A.R.V.I.S.  Wake-on-LAN setup" -ForegroundColor Cyan
Write-Host "  ---------------------------------" -ForegroundColor DarkCyan

# 1. Fast Startup blocks waking from Shutdown, so turn it off
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" /v HiberbootEnabled /t REG_DWORD /d 0 /f | Out-Null
Write-Host "  [OK] Fast Startup turned off" -ForegroundColor Green

# 2. Let every physical network adapter wake the laptop with a magic packet
$adapters = Get-NetAdapter -Physical
if (-not $adapters) { Write-Host "  [!] No network adapters found." -ForegroundColor Yellow }
$ethernet = $null
foreach ($a in $adapters) {
    Set-NetAdapterPowerManagement -Name $a.Name -WakeOnMagicPacket Enabled
    $props = Get-NetAdapterAdvancedProperty -Name $a.Name
    foreach ($p in $props) {
        if ($p.DisplayName -match "(?i)magic packet|wake on lan|wake-on-lan|shutdown wake|wol") {
            foreach ($v in @("Enabled", "On")) {
                if ($p.ValidDisplayValues -contains $v) {
                    Set-NetAdapterAdvancedProperty -Name $a.Name -DisplayName $p.DisplayName -DisplayValue $v
                    break
                }
            }
        }
    }
    powercfg /deviceenablewake "$($a.InterfaceDescription)" 2>$null | Out-Null
    $mac = $a.MacAddress -replace "-", ":"
    $isEth = ($a.MediaType -eq "802.3") -or ($a.Name -match "(?i)ethernet")
    if ($isEth -and -not $ethernet) { $ethernet = $a }
    $kind = if ($isEth) { "ETHERNET" } else { "WI-FI   " }
    Write-Host ("  [OK] {0}  {1}  {2}" -f $kind, $mac, $a.InterfaceDescription) -ForegroundColor Green
}

Write-Host ""
if ($ethernet) {
    Write-Host ("  Use this MAC in the iPhone app:  {0}" -f ($ethernet.MacAddress -replace "-", ":")) -ForegroundColor Cyan
    Write-Host "  Keep the Ethernet cable and the charger plugged in when you shut down." -ForegroundColor Yellow
} else {
    Write-Host "  No Ethernet adapter found. Most laptops can't wake from Shutdown over Wi-Fi." -ForegroundColor Yellow
    Write-Host "  Use 'Jarvis, sleep my laptop' instead, or a USB-Ethernet adapter with Wake-on-LAN." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  LAST STEP (only you can do this): restart, open the BIOS/UEFI setup" -ForegroundColor White
Write-Host "  (usually F2, F10, F12 or Del at boot) and enable 'Wake on LAN'" -ForegroundColor White
Write-Host "  (may be called 'Power On by PCI-E', 'Wake on LAN from S4/S5' or 'Resume by LAN')." -ForegroundColor White
Write-Host ""
