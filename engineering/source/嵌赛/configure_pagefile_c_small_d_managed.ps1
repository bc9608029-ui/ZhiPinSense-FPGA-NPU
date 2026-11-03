$ErrorActionPreference = "Stop"
trap {
    ($_ | Out-String) | Set-Content -LiteralPath 'F:\嵌赛\pagefile_configuration_error.txt' -Encoding UTF8
    exit 1
}

$pagefileIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$pagefilePrincipal = [Security.Principal.WindowsPrincipal]::new($pagefileIdentity)
if (-not $pagefilePrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "This script must be run as Administrator."
}

$pagefileVivado = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match '^vivado' }
if ($pagefileVivado) {
    throw "Vivado is still running; pagefile configuration was not changed."
}

$pagefileDVolume = Get-Volume -DriveLetter D
if ($pagefileDVolume.DriveType -ne 'Fixed' -or $pagefileDVolume.FileSystem -ne 'NTFS') {
    throw "D: is not a fixed NTFS volume; pagefile configuration was not changed."
}
if ($pagefileDVolume.SizeRemaining -lt 80GB) {
    throw "D: has less than 80 GB free; pagefile configuration was not changed."
}

$pagefileBackup = 'F:\嵌赛\pagefile_memory_management_backup_20260930.reg'
if (-not (Test-Path -LiteralPath $pagefileBackup)) {
    throw "The registry backup is missing; pagefile configuration was not changed."
}

$pagefileComputer = Get-CimInstance Win32_ComputerSystem
Set-CimInstance -InputObject $pagefileComputer `
    -Property @{ AutomaticManagedPagefile = $false } | Out-Null

$pagefileSettings = @(Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue)
$pagefileC = $pagefileSettings |
    Where-Object { $_.Name -ieq 'C:\pagefile.sys' } |
    Select-Object -First 1
if ($pagefileC) {
    Set-CimInstance -InputObject $pagefileC `
        -Property @{ InitialSize = [uint32]2048; MaximumSize = [uint32]8192 } | Out-Null
} else {
    New-CimInstance -ClassName Win32_PageFileSetting -Property @{
        Name        = 'C:\pagefile.sys'
        InitialSize = [uint32]2048
        MaximumSize = [uint32]8192
    } | Out-Null
}

$pagefileSettings = @(Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue)
$pagefileD = $pagefileSettings |
    Where-Object { $_.Name -ieq 'D:\pagefile.sys' } |
    Select-Object -First 1
if ($pagefileD) {
    Set-CimInstance -InputObject $pagefileD `
        -Property @{ InitialSize = [uint32]0; MaximumSize = [uint32]0 } | Out-Null
} else {
    New-CimInstance -ClassName Win32_PageFileSetting -Property @{
        Name        = 'D:\pagefile.sys'
        InitialSize = [uint32]0
        MaximumSize = [uint32]0
    } | Out-Null
}

$pagefileResult = @()
$pagefileResult += "AutomaticManagedPagefile=$((Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile)"
$pagefileResult += Get-CimInstance Win32_PageFileSetting |
    Sort-Object Name |
    ForEach-Object { "Name=$($_.Name) InitialSize=$($_.InitialSize) MaximumSize=$($_.MaximumSize)" }
$pagefileResult += "REBOOT_REQUIRED=True"
$pagefileResult | Set-Content -LiteralPath 'F:\嵌赛\pagefile_configuration_result.txt' -Encoding UTF8
$pagefileResult | ForEach-Object { Write-Host $_ }
