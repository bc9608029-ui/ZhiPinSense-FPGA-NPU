param(
    [string]$PortName = "COM12",
    [int]$BaudRate = 115200,
    [string]$SourceFile = "F:\FPGA_Work\sdr_full_chain_12class_ui_v3_m17_3\dist\sdr_full_chain_12class_ui_v3_board_package_m17_3.tar.gz",
    [string]$RemoteFile = "/root/sdr_full_chain_12class_ui_v3_board_package_m17_3.tar.gz"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SourceFile -PathType Leaf)) {
    throw "Source file not found: $SourceFile"
}

$expectedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceFile).Hash.ToLowerInvariant()
$payload = [Convert]::ToBase64String([IO.File]::ReadAllBytes($SourceFile))

$port = [System.IO.Ports.SerialPort]::new(
    $PortName,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$port.Handshake = [System.IO.Ports.Handshake]::None
$port.NewLine = "`n"
$port.ReadTimeout = 250
$port.WriteTimeout = 10000

function Read-Serial([int]$Milliseconds) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $builder = [Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $port.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$builder.Append($chunk)
        }
        Start-Sleep -Milliseconds 40
    }
    return $builder.ToString()
}

try {
    $port.Open()
    $port.DiscardInBuffer()
    $port.WriteLine("")
    Start-Sleep -Milliseconds 400
    $prompt = Read-Serial 600
    if ($prompt -notmatch '(?m)[#$]\s*$') {
        throw "No Linux shell prompt detected on $PortName. Output: $prompt"
    }

    $marker = "__M17_3_B64_$([Guid]::NewGuid().ToString('N'))__"
    $port.WriteLine("base64 -d > '$RemoteFile' <<'$marker'")
    for ($offset = 0; $offset -lt $payload.Length; $offset += 512) {
        $count = [Math]::Min(512, $payload.Length - $offset)
        $port.WriteLine($payload.Substring($offset, $count))
        if (($offset % 4096) -eq 0) {
            Start-Sleep -Milliseconds 30
            [void]$port.ReadExisting()
        }
    }
    $port.WriteLine($marker)
    Start-Sleep -Milliseconds 1200
    [void](Read-Serial 1200)

    $done = "__M17_3_TRANSFER_DONE__"
    $command = "actual=`$(sha256sum '$RemoteFile' | awk '{print `$1}'); " +
               "bytes=`$(wc -c < '$RemoteFile'); " +
               "echo BOARD_SHA256=`$actual BOARD_BYTES=`$bytes; " +
               "test x`$actual = x$expectedHash; rc=`$?; " +
               "printf '${done}:%s\n' `$rc"
    $port.WriteLine($command)
    $output = Read-Serial 15000
    Write-Output $output

    if ($output -notmatch "$done`:0") {
        throw "Board did not confirm matching SHA256"
    }
    Write-Output "TRANSFER_HASH_PASS"
    Write-Output "PC_SHA256=$expectedHash"
    Write-Output "REMOTE_FILE=$RemoteFile"
}
finally {
    if ($port.IsOpen) {
        $port.Close()
    }
    $port.Dispose()
}
