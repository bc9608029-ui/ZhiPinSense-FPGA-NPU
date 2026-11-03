param(
    [Parameter(Mandatory = $true)]
    [string]$SourceFile,

    [Parameter(Mandatory = $true)]
    [string]$RemoteFile,

    [string]$PortName = "COM12",
    [int]$BaudRate = 115200,
    [int]$ChunkBytes = 1024,
    [int]$ChunkDelayMilliseconds = 100
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SourceFile -PathType Leaf)) {
    throw "Source file not found: $SourceFile"
}
if ($ChunkBytes -le 0 -or $ChunkDelayMilliseconds -lt 0) {
    throw "ChunkBytes must be positive and ChunkDelayMilliseconds must be non-negative"
}

$sourceItem = Get-Item -LiteralPath $SourceFile
$expectedBytes = $sourceItem.Length
$expectedHash = (Get-FileHash -LiteralPath $SourceFile -Algorithm SHA256).Hash.ToLowerInvariant()
$payload = [Convert]::ToBase64String(
    [IO.File]::ReadAllBytes($SourceFile),
    [Base64FormattingOptions]::InsertLineBreaks
)
$data = [Text.Encoding]::ASCII.GetBytes($payload)

$serial = [System.IO.Ports.SerialPort]::new(
    $PortName,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.WriteTimeout = 600000
$serial.ReadTimeout = 3000

function Read-UntilMarker {
    param(
        [System.IO.Ports.SerialPort]$Port,
        [string]$Marker,
        [int]$TimeoutSeconds = 120
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $builder = [Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $Port.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$builder.Append($chunk)
            if ($builder.ToString().Contains($Marker)) {
                break
            }
        }
        Start-Sleep -Milliseconds 50
    }
    return $builder.ToString()
}

$echoDisabled = $false
try {
    $serial.Open()
    $serial.DiscardInBuffer()

    # Abort any unfinished command, return to the shell, and suppress Base64 echo.
    $serial.BaseStream.WriteByte(3)
    $serial.BaseStream.Flush()
    Start-Sleep -Milliseconds 500
    $serial.Write("`r`nstty -echo`r`n")
    $echoDisabled = $true
    Start-Sleep -Milliseconds 500
    [void]$serial.ReadExisting()

    Write-Host "SOURCE=$SourceFile"
    Write-Host "REMOTE=$RemoteFile"
    Write-Host "BYTES=$expectedBytes"
    Write-Host "SHA256=$expectedHash"
    Write-Host "Uploading over $PortName at $BaudRate baud. Do not interrupt."

    # base64 reads from the terminal until Ctrl+D (EOF).
    $serial.Write("base64 -d > '$RemoteFile'`r`n")
    Start-Sleep -Milliseconds 500

    for ($offset = 0; $offset -lt $data.Length; $offset += $ChunkBytes) {
        $count = [Math]::Min($ChunkBytes, $data.Length - $offset)
        $serial.Write($data, $offset, $count)
        if ($ChunkDelayMilliseconds -gt 0) {
            Start-Sleep -Milliseconds $ChunkDelayMilliseconds
        }

        if (($offset % 102400) -eq 0) {
            $percent = [Math]::Round(100.0 * $offset / $data.Length, 1)
            Write-Progress -Activity "Serial upload" -Status "$percent%" -PercentComplete $percent
        }
    }

    $serial.Write("`r`n")
    Start-Sleep -Milliseconds 300
    $serial.BaseStream.WriteByte(4)
    $serial.BaseStream.Flush()
    Write-Progress -Activity "Serial upload" -Completed
    Start-Sleep -Seconds 3

    $marker = "__SERIAL_TRANSFER_$([Guid]::NewGuid().ToString('N'))__"
    $verify = "sync; actual_hash=`$(sha256sum '$RemoteFile' | awk '{print `$1}'); " +
              "actual_bytes=`$(wc -c < '$RemoteFile'); " +
              "echo BOARD_SHA256=`$actual_hash BOARD_BYTES=`$actual_bytes; " +
              "if [ x`$actual_hash = x$expectedHash ] && [ x`$actual_bytes = x$expectedBytes ]; " +
              "then echo '${marker}:PASS'; else echo '${marker}:FAIL'; fi"
    $serial.Write("$verify`r`n")
    $response = Read-UntilMarker -Port $serial -Marker $marker -TimeoutSeconds 120
    Write-Output $response

    if (-not $response.Contains("${marker}:PASS")) {
        throw "Board did not confirm matching byte count and SHA256"
    }

    Write-Output "TRANSFER_HASH_PASS"
    Write-Output "PC_SHA256=$expectedHash"
    Write-Output "PC_BYTES=$expectedBytes"
    Write-Output "REMOTE_FILE=$RemoteFile"
}
finally {
    if ($serial.IsOpen) {
        if ($echoDisabled) {
            try {
                $serial.Write("`r`nstty echo`r`n")
                Start-Sleep -Milliseconds 300
            }
            catch {
                # Preserve the original failure; echo can be restored after reconnect.
            }
        }
        $serial.Close()
    }
    $serial.Dispose()
}
