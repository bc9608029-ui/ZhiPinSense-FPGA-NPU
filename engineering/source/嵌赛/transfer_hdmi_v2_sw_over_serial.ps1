param(
    [string]$PortName = "COM12",
    [int]$BaudRate = 115200,
    [string]$SourceDir = "F:\FPGA_Work\hdmi_framebuffer_ui_v2\sw",
    [string]$RemoteDir = "/tmp/hdmi_v2_sw_selftest"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) {
    throw "Source directory not found: $SourceDir"
}

$archive = Join-Path $PSScriptRoot "hdmi_v2_sw_selftest.tar.gz"
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}

& tar.exe -czf $archive -C $SourceDir .
if ($LASTEXITCODE -ne 0) {
    throw "tar.exe failed with exit code $LASTEXITCODE"
}

$expectedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
$payload = [Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
$remoteArchive = "/tmp/hdmi_v2_sw_selftest.tar.gz"

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
$port.WriteTimeout = 5000

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
    [void](Read-Serial 500)

    $port.WriteLine("base64 -d > $remoteArchive <<'__HDMI_V2_B64__'")
    for ($offset = 0; $offset -lt $payload.Length; $offset += 512) {
        $count = [Math]::Min(512, $payload.Length - $offset)
        $port.WriteLine($payload.Substring($offset, $count))
        if (($offset % 4096) -eq 0) {
            Start-Sleep -Milliseconds 30
            [void]$port.ReadExisting()
        }
    }
    $port.WriteLine("__HDMI_V2_B64__")
    Start-Sleep -Milliseconds 1000
    [void](Read-Serial 1000)

    $command = "actual=`$(sha256sum $remoteArchive | awk '{print `$1}'); " +
               "echo BOARD_SHA256=`$actual; " +
               "test x`$actual = x$expectedHash || { echo TRANSFER_HASH_FAIL; exit 9; }; " +
               "mkdir -p $RemoteDir; " +
               "tar -xzf $remoteArchive -C $RemoteDir; " +
               "echo TRANSFER_HASH_PASS; " +
               "ls -1 $RemoteDir"
    $port.WriteLine($command)
    $output = Read-Serial 12000
    Write-Output $output

    if ($output -notmatch "TRANSFER_HASH_PASS") {
        throw "Board did not confirm TRANSFER_HASH_PASS"
    }
    Write-Output "PC_SHA256=$expectedHash"
    Write-Output "REMOTE_DIR=$RemoteDir"
}
finally {
    if ($port.IsOpen) {
        $port.Close()
    }
    $port.Dispose()
}
