$ErrorActionPreference='Stop'
$p=[IO.Ports.SerialPort]::new('COM8',115200)
$p.Open()
try {
  $null=$p.ReadExisting()
  $t0=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()*1000000
  $p.Write("python3 -c 'import time;print(""CLOCK_SYNC"",time.time_ns(),time.monotonic_ns())'`r")
  $buf='';$limit=(Get-Date).AddSeconds(5)
  while((Get-Date) -lt $limit){
    $buf+=$p.ReadExisting()
    if($buf -match 'CLOCK_SYNC\s+(\d{16,20})\s+(\d+)'){
      $t1=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()*1000000
      $board=[decimal]$Matches[1]
      [pscustomobject]@{pc_before_ns=$t0;pc_after_ns=$t1;board_ns=$board;offset_ns=(($t0+$t1)/2-$board);uncertainty_ms=($t1-$t0)/2000000} | ConvertTo-Json
      break
    }
    Start-Sleep -Milliseconds 10
  }
} finally {$p.Close()}
