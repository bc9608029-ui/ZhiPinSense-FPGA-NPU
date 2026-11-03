param(
    [string]$PortName = "COM12",
    [string]$LocalPackage = "F:\FPGA_Work\npu_stage_v1\board_package",
    [string]$RemotePackage = "/home/work/npu_stage_v1"
)

$ErrorActionPreference = "Stop"

function Read-SerialFor {
    param(
        [System.IO.Ports.SerialPort]$Port,
        [int]$Milliseconds
    )
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $text = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $Port.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$text.Append($chunk)
        }
        Start-Sleep -Milliseconds 20
    }
    return $text.ToString()
}

function Invoke-BoardCommand {
    param(
        [System.IO.Ports.SerialPort]$Port,
        [string]$Command,
        [int]$TimeoutSeconds = 30,
        [switch]$Quiet
    )
    $marker = "__CODEX_RC_$([Guid]::NewGuid().ToString('N'))__"
    $wrapped = $Command + "; printf '\n" + $marker + ":%s\n' `$?"
    $Port.Write($wrapped + "`r")

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $text = [System.Text.StringBuilder]::new()
    $match = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $Port.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$text.Append($chunk)
            if (-not $Quiet) {
                Write-Host -NoNewline $chunk
            }
            $match = [regex]::Match($text.ToString(), [regex]::Escape($marker) + ":([0-9]+)")
            if ($match.Success) {
                return [pscustomobject]@{
                    ExitCode = [int]$match.Groups[1].Value
                    Output = $text.ToString()
                }
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
    $quotedRemote = "'$RemotePath'"
    $quotedB64 = "'$remoteB64'"

    $result = Invoke-BoardCommand -Port $Port -Command "rm -f $quotedB64 '$RemotePath.codex.tmp'" -TimeoutSeconds 10 -Quiet
    if ($result.ExitCode -ne 0) { throw "Unable to initialize upload for $RemotePath" }

    $chunkSize = 768
    for ($offset = 0; $offset -lt $base64.Length; $offset += $chunkSize) {
        $length = [Math]::Min($chunkSize, $base64.Length - $offset)
        $chunk = $base64.Substring($offset, $length)
        $result = Invoke-BoardCommand -Port $Port -Command "printf '%s' '$chunk' >> $quotedB64" -TimeoutSeconds 10 -Quiet
        if ($result.ExitCode -ne 0) { throw "Upload chunk failed for $RemotePath at offset $offset" }
    }

    $result = Invoke-BoardCommand -Port $Port -Command "base64 -d $quotedB64 > '$RemotePath.codex.tmp' && mv '$RemotePath.codex.tmp' $quotedRemote && rm -f $quotedB64" -TimeoutSeconds 20 -Quiet
    if ($result.ExitCode -ne 0) { throw "Decode failed for $RemotePath" }

    $expected = (Get-FileHash -Algorithm SHA256 -LiteralPath $LocalPath).Hash.ToLowerInvariant()
    $result = Invoke-BoardCommand -Port $Port -Command "sha256sum $quotedRemote" -TimeoutSeconds 10 -Quiet
    if ($result.ExitCode -ne 0 -or $result.Output.ToLowerInvariant() -notmatch [regex]::Escape($expected)) {
        throw "SHA-256 verification failed for $RemotePath (expected $expected)"
    }
    Write-Host "UPLOAD_OK $([IO.Path]::GetFileName($LocalPath)) $expected"
}

$filesToUpload = @(
    "npu_only_smoke.cpp",
    "CMakeLists.txt",
    "run_all_frames.sh",
    "README.md",
    "sha256_manifest.txt"
)

$port = [System.IO.Ports.SerialPort]::new(
    $PortName,
    115200,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
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
    if ($prompt -notmatch "root@U") {
        throw "The board root shell prompt was not detected on $PortName"
    }

    $precheck = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && pwd && sha256sum model.json model.raw expected_tensor_plddr.bin reference_argmax.txt && test -f run_frame7.sh && test -f build_on_board.sh" -TimeoutSeconds 30
    if ($precheck.ExitCode -ne 0) { throw "Board package precheck failed" }

    $backup = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && mkdir -p pre_per_frame_fix && cp -f npu_only_smoke.cpp CMakeLists.txt run_all_frames.sh README.md sha256_manifest.txt pre_per_frame_fix/ 2>/dev/null || true" -TimeoutSeconds 20 -Quiet
    foreach ($name in $filesToUpload) {
        Send-BoardFile -Port $port -LocalPath (Join-Path $LocalPackage $name) -RemotePath "$RemotePackage/$name"
    }

    $verify = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && sha256sum -c sha256_manifest.txt && chmod +x build_on_board.sh run_frame7.sh run_all_frames.sh" -TimeoutSeconds 60
    if ($verify.ExitCode -ne 0) { throw "Full board-package hash verification failed" }

    Write-Host "`n=== BUILD ==="
    $build = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./build_on_board.sh" -TimeoutSeconds 300
    if ($build.ExitCode -ne 0) { throw "Board build failed with exit code $($build.ExitCode)" }

    Write-Host "`n=== FRAME 7 ==="
    $frame7 = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./run_frame7.sh" -TimeoutSeconds 120
    if ($frame7.ExitCode -ne 0 -or $frame7.Output -notmatch "V2_NPU_ONLY_SMOKE_REFERENCE_MATCH") {
        throw "Frame 7 hardware test failed"
    }

    Write-Host "`n=== FRAMES 7-18 ==="
    $all = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./run_all_frames.sh" -TimeoutSeconds 300
    if ($all.ExitCode -ne 0 -or $all.Output -notmatch "class_match=12/12" -or $all.Output -notmatch "V2_NPU_ONLY_SMOKE_REFERENCE_MATCH") {
        throw "Continuous frames 7-18 hardware test failed"
    }

    Write-Host "`n=== SAFE FLUSH ==="
    $sync = Invoke-BoardCommand -Port $port -Command "sync" -TimeoutSeconds 30
    if ($sync.ExitCode -ne 0) { throw "sync failed" }

    Write-Host "`nNPU_RETEST_PASS"
} finally {
    if ($port.IsOpen) { $port.Close() }
}
