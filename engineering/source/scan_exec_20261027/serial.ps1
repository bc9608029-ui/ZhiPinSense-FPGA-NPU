param([string]$Command,[int]$Seconds=3)
$ErrorActionPreference='Stop'
$p=[IO.Ports.SerialPort]::new('COM8',115200);$p.ReadBufferSize=1048576;$p.WriteTimeout=5000
$p.Open();try{$null=$p.ReadExisting();$p.Write($Command+"`r");$end=(Get-Date).AddSeconds($Seconds);while((Get-Date)-lt $end){$t=$p.ReadExisting();if($t){Write-Output $t};Start-Sleep -Milliseconds 100}}finally{$p.Close()}