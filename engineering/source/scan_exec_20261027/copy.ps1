param([string]$Remote,[string]$Local)
$ErrorActionPreference='Stop'
if($Remote -notmatch '^/root/rml24_scan_execution_20261027/[a-zA-Z0-9_./-]+$'){throw 'Invalid evidence path'}
$c = @"
python3 -c 'import pathlib,hashlib,gzip,base64;b=pathlib.Path("$Remote").read_bytes();print("__COPY_BEGIN__ "+hashlib.sha256(b).hexdigest());print(base64.b64encode(gzip.compress(b)).decode());print("__COPY_END__")'
"@
$p=[IO.Ports.SerialPort]::new('COM8',115200);$p.ReadBufferSize=1048576;$p.WriteTimeout=5000;$p.Open();$text=''
try{$null=$p.ReadExisting();$p.Write($c+"`r");$end=(Get-Date).AddSeconds(55);while((Get-Date)-lt $end){$text+=$p.ReadExisting();if($text -match '(?s)__COPY_BEGIN__ ([a-f0-9]{64})\s+([A-Za-z0-9+/=\r\n]+)\s+__COPY_END__'){break};Start-Sleep -Milliseconds 50}}finally{$p.Close()}
if($text -notmatch '(?s)__COPY_BEGIN__ ([a-f0-9]{64})\s+([A-Za-z0-9+/=\r\n]+)\s+__COPY_END__'){throw 'Incomplete copy'}
$sha=$Matches[1];$m=[IO.MemoryStream]::new([Convert]::FromBase64String(($Matches[2]-replace '\s','')));$g=[IO.Compression.GzipStream]::new($m,[IO.Compression.CompressionMode]::Decompress);$o=[IO.MemoryStream]::new();$g.CopyTo($o);$g.Dispose();[IO.File]::WriteAllBytes($Local,$o.ToArray());$o.Dispose();$m.Dispose();if((Get-FileHash -LiteralPath $Local).Hash.ToLower()-ne $sha){throw 'SHA mismatch'};Write-Output "EVIDENCE_COPY_PASS=$Local SHA=$sha"