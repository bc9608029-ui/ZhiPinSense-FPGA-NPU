$ErrorActionPreference='Stop'
$p=[IO.Ports.SerialPort]::new('COM8',115200)
$p.ReadBufferSize=1048576
$p.Open()
try {
 $null=$p.ReadExisting()
 $samples=@()
 for($i=0;$i -lt 5;$i++){
  $token='MONO_SYNC_'+([Guid]::NewGuid().ToString('N').Substring(0,10))
  $t0=[Diagnostics.Stopwatch]::GetTimestamp()
  $p.Write("python3 -c 'import time;print(""$token"",time.monotonic_ns(),time.time_ns(),open(""/proc/sys/kernel/random/boot_id"").read().strip())'`r")
  $buf='';$timer=[Diagnostics.Stopwatch]::StartNew();$found=$false
  while($timer.Elapsed.TotalSeconds -lt 5){
   $buf+=$p.ReadExisting()
   if($buf -match ($token+'\s+(\d+)\s+(\d{16,20})\s+([a-f0-9-]{36})')){
    $t1=[Diagnostics.Stopwatch]::GetTimestamp()
    $freq=[decimal][Diagnostics.Stopwatch]::Frequency
    $a=[decimal]$t0*1000000000/$freq;$b=[decimal]$t1*1000000000/$freq
    $samples+=[pscustomobject]@{pc_before_mono_ns=[long]$a;pc_after_mono_ns=[long]$b;board_mono_ns=[long]$Matches[1];board_wall_ns=$Matches[2];board_boot_id=$Matches[3];offset_ns=[long](($a+$b)/2-[decimal]$Matches[1]);uncertainty_ns=[long](($b-$a)/2)}
    $found=$true;break
   }
   Start-Sleep -Milliseconds 5
  }
  if(-not $found){throw 'Monotonic serial synchronization timeout'}
 }
 $best=$samples | Sort-Object uncertainty_ns | Select-Object -First 1
 [pscustomobject]@{clock_id='windows-qpc-board-monotonic-v1';offset_ns=$best.offset_ns;uncertainty_ns=$best.uncertainty_ns;board_boot_id=$best.board_boot_id;samples=$samples} | ConvertTo-Json -Depth 5
}finally{$p.Close()}
