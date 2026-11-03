param([switch]$Reboot)
$ErrorActionPreference='Stop'
$p=[IO.Ports.SerialPort]::new('COM8',115200)
$p.ReadBufferSize=1048576
$p.WriteTimeout=3000
$path=Join-Path (Split-Path -Parent $PSScriptRoot) 'evidence\cold_power_serial_01.txt'
$writer=[IO.StreamWriter]::new($path,$false,[Text.UTF8Encoding]::new($false))
$writer.AutoFlush=$true
$p.Open()
try {
 $initial=$p.ReadExisting();$writer.Write($initial)
 $p.Write("systemctl poweroff`r")
 $deadline=(Get-Date).AddSeconds(180)
 while((Get-Date) -lt $deadline){
  try { if(-not $p.IsOpen){$p.Open()}; $s=$p.ReadExisting() } catch { try{$p.Close()}catch{}; Start-Sleep -Milliseconds 500; continue }
  if($s){$writer.Write($s);$lines=$s -split "`n";foreach($line in $lines){if($line -match 'RML24_BOOT|U-Boot|FPGA|fpga|login:|Failed to|Starting RML24|Started RML24|ERROR|Power down|Powering off'){Write-Output $line}}}
  Start-Sleep -Milliseconds 100
 }
} finally {$p.Close();$writer.Dispose()}
Write-Output 'REBOOT_CAPTURE_COMPLETE'