param([string]$Command,[int]$Seconds=3)
$ErrorActionPreference='Stop'
$serialMutex=[Threading.Mutex]::new($false,'Local\Rml24BoardSerialCOM8')
$serialHeld=$false
try {
 try { $serialHeld=$serialMutex.WaitOne(60000) } catch [Threading.AbandonedMutexException] { $serialHeld=$true }
 if (-not $serialHeld) { throw 'Timed out waiting for exclusive COM8 access' }
 for ($serialAttempt=0;$serialAttempt -lt 10;$serialAttempt++) {
  try { & E:\scan_exec_20261027\serial.ps1 -Command $Command -Seconds $Seconds; break }
  catch {
   if ($_.Exception.Message -match 'Access to the port.*COM8.*denied' -and $serialAttempt -lt 9) { Start-Sleep -Milliseconds 1000 }
   else { throw }
  }
 }
} finally { if ($serialHeld) { $serialMutex.ReleaseMutex() }; $serialMutex.Dispose() }
