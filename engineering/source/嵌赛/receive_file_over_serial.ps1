param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteFile,

    [Parameter(Mandatory = $true)]
    [string]$DestinationFile,

    [string]$PortName = "COM12",
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 1800,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if ($RemoteFile -notmatch '^/[A-Za-z0-9._/+\-]+$') {
    throw "RemoteFile must be an absolute Linux path containing only safe path characters"
}
if ($TimeoutSeconds -le 0) {
    throw "TimeoutSeconds must be positive"
}

$destinationPath = [IO.Path]::GetFullPath($DestinationFile)
$destinationDirectory = Split-Path -Parent $destinationPath
if (-not (Test-Path -LiteralPath $destinationDirectory -PathType Container)) {
    throw "Destination directory does not exist: $destinationDirectory"
}
if ((Test-Path -LiteralPath $destinationPath) -and -not $Force) {
    throw "Destination already exists; remove it or pass -Force: $destinationPath"
}

$partialPath = "$destinationPath.partial.$([Guid]::NewGuid().ToString('N'))"
$token = [Guid]::NewGuid().ToString('N')
$beginMarker = "__SERIAL_DOWNLOAD_BEGIN_${token}__"
$endMarker = "__SERIAL_DOWNLOAD_END_${token}__"

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
$serial.ReadTimeout = 1000
$serial.WriteTimeout = 5000

$echoDisabled = $false
try {
    $serial.Open()
    $serial.DiscardInBuffer()

    # Return to an idle shell and prevent the command itself from being echoed
    # into the Base64 payload.
    $serial.BaseStream.WriteByte(3)
    $serial.BaseStream.Flush()
    Start-Sleep -Milliseconds 500
    $serial.Write("`r`nstty -echo`r`n")
    $echoDisabled = $true
    Start-Sleep -Milliseconds 500
    [void]$serial.ReadExisting()

    $command = "if [ ! -f '$RemoteFile' ]; then " +
        "printf '%s\n' '$beginMarker ERROR=NOT_FOUND'; " +
        "printf '%s\n' '$endMarker'; " +
        "else b=`$(wc -c < '$RemoteFile'); " +
        "h=`$(sha256sum '$RemoteFile' | awk '{print `$1}'); " +
        "printf '%s BYTES=%s SHA256=%s\n' '$beginMarker' `"`$b`" `"`$h`"; " +
        "base64 -w 76 '$RemoteFile'; " +
        "printf '\n%s\n' '$endMarker'; fi"

    Write-Host "REMOTE=$RemoteFile"
    Write-Host "DESTINATION=$destinationPath"
    Write-Host "Downloading over $PortName at $BaudRate baud. Do not interrupt."
    $serial.Write("$command`r`n")

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $response = [Text.StringBuilder]::new()
    $foundEnd = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $serial.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$response.Append($chunk)
            $received = $response.Length
            Write-Progress -Activity "Serial download" -Status "$received encoded characters received"

            # Search only after receiving new data. The bundle is small enough
            # that retaining the encoded response is safe and simplifies strict
            # marker validation.
            if ($response.ToString().Contains($endMarker)) {
                $foundEnd = $true
                break
            }
        }
        Start-Sleep -Milliseconds 20
    }
    Write-Progress -Activity "Serial download" -Completed

    if (-not $foundEnd) {
        throw "Timed out before the board sent the end marker"
    }

    $text = $response.ToString()
    $beginIndex = $text.IndexOf($beginMarker, [StringComparison]::Ordinal)
    if ($beginIndex -lt 0) {
        throw "Board response did not contain the begin marker"
    }
    $headerEnd = $text.IndexOf("`n", $beginIndex)
    if ($headerEnd -lt 0) {
        throw "Board response contained an incomplete metadata header"
    }
    $header = $text.Substring($beginIndex, $headerEnd - $beginIndex).Trim()
    if ($header -match 'ERROR=NOT_FOUND') {
        throw "Remote file does not exist: $RemoteFile"
    }
    if ($header -notmatch 'BYTES=([0-9]+) SHA256=([0-9a-fA-F]{64})$') {
        throw "Invalid board metadata header: $header"
    }

    $expectedBytes = [Int64]$Matches[1]
    $expectedHash = $Matches[2].ToLowerInvariant()
    $payloadStart = $headerEnd + 1
    $endIndex = $text.IndexOf($endMarker, $payloadStart, [StringComparison]::Ordinal)
    if ($endIndex -lt 0) {
        throw "Board response did not contain a valid end marker"
    }

    $base64Text = $text.Substring($payloadStart, $endIndex - $payloadStart).Trim()
    try {
        $bytes = [Convert]::FromBase64String($base64Text)
    }
    catch {
        throw "Received Base64 data is incomplete or corrupt: $($_.Exception.Message)"
    }

    if ($bytes.LongLength -ne $expectedBytes) {
        throw "Byte-count mismatch: board=$expectedBytes received=$($bytes.LongLength)"
    }

    [IO.File]::WriteAllBytes($partialPath, $bytes)
    $actualHash = (Get-FileHash -LiteralPath $partialPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "SHA256 mismatch: board=$expectedHash received=$actualHash"
    }

    Move-Item -LiteralPath $partialPath -Destination $destinationPath -Force:$Force
    Write-Output "SERIAL_DOWNLOAD_HASH_PASS"
    Write-Output "BOARD_SHA256=$expectedHash"
    Write-Output "PC_SHA256=$actualHash"
    Write-Output "BYTES=$expectedBytes"
    Write-Output "DESTINATION_FILE=$destinationPath"
}
finally {
    if (Test-Path -LiteralPath $partialPath) {
        Remove-Item -LiteralPath $partialPath -Force
    }
    if ($serial.IsOpen) {
        if ($echoDisabled) {
            try {
                $serial.Write("`r`nstty echo`r`n")
                Start-Sleep -Milliseconds 300
            }
            catch {
                # Preserve the original error. Echo can be restored after reconnect.
            }
        }
        $serial.Close()
    }
    $serial.Dispose()
}
