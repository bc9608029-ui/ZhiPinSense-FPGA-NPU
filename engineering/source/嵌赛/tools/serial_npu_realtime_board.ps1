param(
    [string]$PortName = "COM12",
    [string]$LocalPackage = "F:\FPGA_Work\npu_realtime_v1\board_package",
    [string]$AssetSource = "/home/work/npu_diag_v1",
    [string]$RemotePackage = "/home/work/npu_realtime_v1",
    [switch]$Resume
)

$ErrorActionPreference = "Stop"

function Read-SerialFor {
    param([System.IO.Ports.SerialPort]$Port, [int]$Milliseconds)
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $text = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $Port.ReadExisting()
        if ($chunk.Length -gt 0) { [void]$text.Append($chunk) }
        Start-Sleep -Milliseconds 20
    }
    $text.ToString()
}

function Invoke-BoardCommand {
    param(
        [System.IO.Ports.SerialPort]$Port,
        [string]$Command,
        [int]$TimeoutSeconds = 60,
        [switch]$Quiet
    )
    $marker = "__CODEX_RC_$([Guid]::NewGuid().ToString('N'))__"
    $wrapped = $Command + "; printf '\n" + $marker + ":%s\n' `$?"
    $Port.Write($wrapped + "`r")
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $text = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $Port.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$text.Append($chunk)
            if (-not $Quiet) { Write-Host -NoNewline $chunk }
            $match = [regex]::Match($text.ToString(), [regex]::Escape($marker) + ":([0-9]+)")
            if ($match.Success) {
                return [pscustomobject]@{ ExitCode = [int]$match.Groups[1].Value; Output = $text.ToString() }
            }
        }
        Start-Sleep -Milliseconds 20
    }
    throw "Timed out after $TimeoutSeconds seconds: $Command"
}

function Send-BoardFile {
    param(
        [System.IO.Ports.SerialPort]$Port,
        [string]$LocalPath,
        [string]$RemotePath
    )
    $bytes = [System.IO.File]::ReadAllBytes($LocalPath)
    $base64 = [Convert]::ToBase64String($bytes)
    $remoteB64 = "$RemotePath.codex.b64"
    $result = Invoke-BoardCommand -Port $Port -Command "rm -f '$remoteB64' '$RemotePath.codex.tmp'" -TimeoutSeconds 10 -Quiet
    if ($result.ExitCode -ne 0) { throw "Unable to initialize upload for $RemotePath" }

    $chunkSize = 768
    for ($offset = 0; $offset -lt $base64.Length; $offset += $chunkSize) {
        $length = [Math]::Min($chunkSize, $base64.Length - $offset)
        $chunk = $base64.Substring($offset, $length)
        $result = Invoke-BoardCommand -Port $Port -Command "printf '%s' '$chunk' >> '$remoteB64'" -TimeoutSeconds 10 -Quiet
        if ($result.ExitCode -ne 0) { throw "Upload chunk failed for $RemotePath at offset $offset" }
    }

    $result = Invoke-BoardCommand -Port $Port -Command "base64 -d '$remoteB64' > '$RemotePath.codex.tmp' && mv '$RemotePath.codex.tmp' '$RemotePath' && rm -f '$remoteB64'" -TimeoutSeconds 30 -Quiet
    if ($result.ExitCode -ne 0) { throw "Decode failed for $RemotePath" }

    $expected = (Get-FileHash -Algorithm SHA256 -LiteralPath $LocalPath).Hash.ToLowerInvariant()
    $result = Invoke-BoardCommand -Port $Port -Command "sha256sum '$RemotePath'" -TimeoutSeconds 10 -Quiet
    if ($result.ExitCode -ne 0 -or $result.Output.ToLowerInvariant() -notmatch [regex]::Escape($expected)) {
        throw "SHA-256 verification failed for $RemotePath"
    }
    Write-Host "UPLOAD_OK $([IO.Path]::GetFileName($LocalPath)) $expected"
}

$uploadFiles = @(
    "npu_realtime.cpp",
    "CMakeLists.txt",
    "build_on_board.sh",
    "run_rearm_sweep.sh",
    "run_realtime.sh",
    "README.md",
    "REPORT.md",
    "sha256_manifest.txt"
)

$port = [System.IO.Ports.SerialPort]::new(
    $PortName, 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One
)
$port.ReadTimeout = 200
$port.WriteTimeout = 5000
$port.Handshake = [System.IO.Ports.Handshake]::None
$port.DtrEnable = $false
$port.RtsEnable = $false

try {
    $port.Open()
    [void](Read-SerialFor -Port $port -Milliseconds 300)
    $port.Write("`r")
    $prompt = Read-SerialFor -Port $port -Milliseconds 1000
    Write-Host $prompt
    if ($prompt -notmatch "root@U") { throw "Board root prompt not detected" }

    $assetCheck = Invoke-BoardCommand -Port $port -Command "sha256sum '$AssetSource/model.json' '$AssetSource/model.raw' '$AssetSource/reference_argmax.txt' '$AssetSource/expected_tensor_plddr.bin'" -TimeoutSeconds 30
    if ($assetCheck.ExitCode -ne 0) { throw "Verified board assets are unavailable" }

    if ($Resume) {
        $existing = Invoke-BoardCommand -Port $port -Command "test -d '$RemotePackage'" -TimeoutSeconds 20
        if ($existing.ExitCode -ne 0) { throw "Resume requested but remote realtime directory does not exist" }
    } else {
        $create = Invoke-BoardCommand -Port $port -Command "if [ -e '$RemotePackage' ]; then echo '__REMOTE_DIR_ALREADY_EXISTS__'; exit 73; else mkdir '$RemotePackage'; fi" -TimeoutSeconds 20
        if ($create.ExitCode -ne 0) { throw "Remote realtime directory is not new; stopped without deleting it" }
    }

    $copy = Invoke-BoardCommand -Port $port -Command "cp '$AssetSource/model.json' '$RemotePackage/model.json' && cp '$AssetSource/model.raw' '$RemotePackage/model.raw' && cp '$AssetSource/reference_argmax.txt' '$RemotePackage/reference_argmax.txt' && cp '$AssetSource/expected_tensor_plddr.bin' '$RemotePackage/tensor_19frames_sint8.bin'" -TimeoutSeconds 30
    if ($copy.ExitCode -ne 0) { throw "Failed to copy immutable board assets" }

    foreach ($name in $uploadFiles) {
        Send-BoardFile -Port $port -LocalPath (Join-Path $LocalPackage $name) -RemotePath "$RemotePackage/$name"
    }

    $verify = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && sha256sum -c sha256_manifest.txt && chmod +x build_on_board.sh run_rearm_sweep.sh run_realtime.sh" -TimeoutSeconds 90
    if ($verify.ExitCode -ne 0) { throw "Board-package integrity gate failed" }

    Write-Host "`n=== BUILD ==="
    $build = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./build_on_board.sh && ls -l --time-style=full-iso build/npu_realtime && sha256sum build/npu_realtime" -TimeoutSeconds 420
    if ($build.ExitCode -ne 0) { throw "Realtime board build failed" }

    Write-Host "`n=== RE-ARM SWEEP ==="
    $sweep = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./run_rearm_sweep.sh" -TimeoutSeconds 1200

    Write-Host "`n=== SWEEP RESULT LINES ==="
    $lines = ($sweep.Output -split "`r?`n" | Where-Object { $_ -match '^(===== rearm=|RT_SUMMARY|RT_ALT_SUMMARY|RT_RESULT=|sweep summary)' })
    $lines | ForEach-Object { Write-Host $_ }

    $sync = Invoke-BoardCommand -Port $port -Command "sync" -TimeoutSeconds 30
    if ($sync.ExitCode -ne 0) { throw "sync failed" }

    Write-Host "`nNPU_REALTIME_SWEEP_COMPLETE sweep_rc=$($sweep.ExitCode)"
} finally {
    if ($port.IsOpen) { $port.Close() }
}
