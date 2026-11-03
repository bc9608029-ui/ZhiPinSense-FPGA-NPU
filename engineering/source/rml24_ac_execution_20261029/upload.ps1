param([string]$Local,[string]$Remote)
$ErrorActionPreference='Stop'
if($Remote -notmatch '^/root/rml24_ac_execution_20261029/[a-zA-Z0-9_./-]+$'){throw 'Invalid target'}
$b=[Convert]::ToBase64String([IO.File]::ReadAllBytes($Local));$p=[IO.Ports.SerialPort]::new('COM8',115200);$p.ReadBufferSize=1048576;$p.WriteTimeout=5000;$p.Open()
try{$null=$p.ReadExisting();$p.Write("stty -echo; base64 -d > $Remote <<'RML24_SCRIPT_END'`r");Start-Sleep -Milliseconds 200;for($i=0;$i -lt $b.Length;$i+=800){$p.Write($b.Substring($i,[Math]::Min(800,$b.Length-$i))+"`r");Start-Sleep -Milliseconds 100;$null=$p.ReadExisting()};$p.Write("RML24_SCRIPT_END`rstty echo`rsha256sum $Remote`r");Start-Sleep -Milliseconds 500;$p.ReadExisting()}finally{$p.Close()}

