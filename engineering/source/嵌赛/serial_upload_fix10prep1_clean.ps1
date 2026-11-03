$ErrorActionPreference = 'Stop'
$PortName = 'COM12'
$BaudRate = 115200
$ChunkChars = 3000
$AckTimeoutSeconds = 30

$Uploads = @(
    @{
        Source = Join-Path $PSScriptRoot 'fix10prep1_clean_work\sdr_rml23_live_board_package_iq_rf_loopback_fix10prep1_clean\dist\sdr_rml23_live_board_package_clean_iq_fix10prep1.tar.gz'
        Destination = '/root/sdr_rml23_live_board_package_clean_iq_fix10prep1.tar.gz'
        Sha256 = 'c8cbaadd98d9a508aa92ff8707e4ab6dbfc6c8ee84661efda4925726533b3039'
    },
    @{
        Source = Join-Path $PSScriptRoot 'fix10_clean24_fix10prep1.tar.gz'
        Destination = '/root/fix10_clean24_fix10prep1.tar.gz'
        Sha256 = 'f3cb53dc7da7a7df9c293788a409369fd5255a6a57e4db27578b849c2b1ab924'
    }
)

function Write-SerialLine {
    param([System.IO.Ports.SerialPort]$Port, [string]$Text)
    $bytes = [Text.Encoding]::ASCII.GetBytes($Text + "`r`n")
    $Port.BaseStream.Write($bytes, 0, $bytes.Length)
    $Port.BaseStream.Flush()
}

function Wait-SerialMarker {
    param([System.IO.Ports.SerialPort]$Port, [string]$Marker, [int]$TimeoutSeconds)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $received = ''
    while ([DateTime]::UtcNow -lt $deadline) {
        $part = $Port.ReadExisting()
        if ($part.Length -gt 0) {
            $received += $part
            if ($received.Contains($Marker)) { return $received }
            if ($received.Length -gt 65536) {
                $received = $received.Substring($received.Length - 32768)
            }
        }
        Start-Sleep -Milliseconds 20
    }
    throw "Timed out waiting for board ACK: $Marker; recent output: $received"
}

foreach ($upload in $Uploads) {
    if (-not (Test-Path -LiteralPath $upload.Source -PathType Leaf)) {
        throw "Local file not found: $($upload.Source)"
    }
    $actual = (Get-FileHash -LiteralPath $upload.Source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $upload.Sha256) {
        throw "Local SHA mismatch: $($upload.Source) actual=$actual expected=$($upload.Sha256)"
    }
}

$port = New-Object System.IO.Ports.SerialPort $PortName,$BaudRate,'None',8,'One'
$port.Handshake = 'None'
$port.DtrEnable = $false
$port.RtsEnable = $false
$port.WriteTimeout = 60000
$port.ReadTimeout = 500
$port.Encoding = [Text.Encoding]::ASCII

try {
    $port.Open()
    Start-Sleep -Milliseconds 500
    [void]$port.ReadExisting()

    $sessionMarker = '__CODEX_SERIAL_READY_' + [Guid]::NewGuid().ToString('N') + '__'
    Write-SerialLine $port "stty -echo; printf '\n$sessionMarker\n'"
    [void](Wait-SerialMarker $port $sessionMarker 10)

    foreach ($upload in $Uploads) {
        $source = $upload.Source
        $destination = $upload.Destination
        $sidecar = $destination + '.b64'
        $temporary = $destination + '.tmp'
        $fileId = [Guid]::NewGuid().ToString('N')
        $raw = [IO.File]::ReadAllBytes($source)
        $base64 = [Convert]::ToBase64String($raw)
        $totalChunks = [int][Math]::Ceiling($base64.Length / [double]$ChunkChars)

        $initMarker = "__INIT_${fileId}__"
        Write-SerialLine $port "rm -f '$sidecar' '$temporary'; printf '$initMarker\n'"
        [void](Wait-SerialMarker $port $initMarker 10)
        Write-Host "Uploading $source -> $destination"
        Write-Host "Chunks: $totalChunks. Serial speed is 115200 baud."

        for ($index = 0; $index -lt $totalChunks; $index++) {
            $offset = $index * $ChunkChars
            $length = [Math]::Min($ChunkChars, $base64.Length - $offset)
            $chunk = $base64.Substring($offset, $length)
            $ack = "__ACK_${fileId}_${index}__"
            Write-SerialLine $port "printf '%s' '$chunk' >> '$sidecar'; printf '$ack\n'"
            [void](Wait-SerialMarker $port $ack $AckTimeoutSeconds)
            $percent = [Math]::Round(100.0 * ($index + 1) / $totalChunks, 1)
            Write-Progress -Activity "Serial upload $(Split-Path $source -Leaf)" `
                -Status "$($index + 1)/$totalChunks ($($percent) percent)" `
                -PercentComplete $percent
        }
        Write-Progress -Activity "Serial upload $(Split-Path $source -Leaf)" -Completed

        $doneMarker = "__DONE_${fileId}__"
        $finish = "base64 -d '$sidecar' > '$temporary' && " +
                  "echo '$($upload.Sha256) *$temporary' | sha256sum -c - >/dev/null 2>&1 && " +
                  "mv '$temporary' '$destination'; " +
                  "rc=`$?; rm -f '$sidecar' '$temporary'; sync; " +
                  "printf '${doneMarker}:%s\n' `$rc"
        Write-SerialLine $port $finish
        $response = Wait-SerialMarker $port $doneMarker 120
        if (-not $response.Contains("${doneMarker}:0")) {
            throw "Board decode or SHA verification failed: $destination; output: $response"
        }
        Write-Host "Board SHA verified: $destination"
    }

    $finalMarker = '__CODEX_UPLOAD_ALL_OK__'
    Write-SerialLine $port "stty echo; printf '\n$finalMarker\n'"
    [void](Wait-SerialMarker $port $finalMarker 10)
    Write-Host 'UPLOAD_RESULT=PASS; both files passed SHA256 verification on the board.'
}
finally {
    if ($port.IsOpen) { $port.Close() }
}
