$ErrorActionPreference='Stop'
$p=[IO.Ports.SerialPort]::new('COM8',115200)
$p.ReadBufferSize=1048576
$p.Open()
try {
  $null=$p.ReadExisting()
  $p.Write("/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/emit_multifreq_sweep.py`r")
  $buf='';$limit=(Get-Date).AddSeconds(55)
  while((Get-Date)-lt $limit){
    $buf+=$p.ReadExisting()
    if($buf -match '(?s)EVIDENCE_BEGIN\r?\n([A-Za-z0-9+/=\r\n]+)EVIDENCE_END'){
      $payload=$Matches[1] -replace '\s',''
      [IO.File]::WriteAllBytes('E:\rml24_three_modes_execution_20261029\multifreq_sweep01_evidence.json.gz',[Convert]::FromBase64String($payload))
      Write-Output 'EVIDENCE_COLLECTED'
      return
    }
    Start-Sleep -Milliseconds 20
  }
  throw 'Evidence export timed out'
} finally {$p.Close()}

