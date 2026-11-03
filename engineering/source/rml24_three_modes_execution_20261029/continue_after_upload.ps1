$ErrorActionPreference='Stop'
$ready=$false
for($i=0;$i -lt 600;$i++) { $p=[IO.Ports.SerialPort]::new('COM8',115200);try{$p.Open();$p.Close();$ready=$true;break}catch{Start-Sleep -Milliseconds 500}finally{$p.Dispose()} }
if(-not $ready){throw 'Serial still busy; stages not started'}
& 'E:\rml24_three_modes_execution_20261029\upload.ps1' -Local 'E:\rml24_three_modes_execution_20261029\board_stages.py' -Remote '/root/rml24_three_modes_execution_20261029/board_stages.py'
& 'E:\scan_exec_20261027\serial.ps1' -Command 'nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/board_stages.py > /root/rml24_three_modes_execution_20261029/stages.log 2>&1 < /dev/null & echo THREE_MODE_STAGES_PID=$!' -Seconds 3
