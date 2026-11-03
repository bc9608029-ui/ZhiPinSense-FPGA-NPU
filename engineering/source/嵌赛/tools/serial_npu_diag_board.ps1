param(
    [string]$PortName = "COM12",
    [string]$LocalPackage = "F:\FPGA_Work\npu_stage_v1\board_package",
    [string]$OldRemotePackage = "/home/work/npu_stage_v1",
    [string]$RemotePackage = "/home/work/npu_diag_v1"
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

    $result = Invoke-BoardCommand -Port $Port -Command "base64 -d '$remoteB64' > '$RemotePath.codex.tmp' && mv '$RemotePath.codex.tmp' '$RemotePath' && rm -f '$remoteB64'" -TimeoutSeconds 20 -Quiet
    if ($result.ExitCode -ne 0) { throw "Decode failed for $RemotePath" }

    $expected = (Get-FileHash -Algorithm SHA256 -LiteralPath $LocalPath).Hash.ToLowerInvariant()
    $result = Invoke-BoardCommand -Port $Port -Command "sha256sum '$RemotePath'" -TimeoutSeconds 10 -Quiet
    if ($result.ExitCode -ne 0 -or $result.Output.ToLowerInvariant() -notmatch [regex]::Escape($expected)) {
        throw "SHA-256 verification failed for $RemotePath"
    }
    Write-Host "UPLOAD_OK $([IO.Path]::GetFileName($LocalPath)) $expected"
}

$uploadFiles = @(
    "CMakeLists.txt",
    "README.md",
    "build_on_board.sh",
    "npu_diag.cpp",
    "npu_only_smoke.cpp",
    "run_diagnostic.sh",
    "run_frame7.sh",
    "run_process_baseline.sh",
    "sha256_manifest.txt"
)

$copyFiles = @(
    "expected_tensor_plddr.bin",
    "model.json",
    "model.raw",
    "pc_reference_19frames.csv",
    "pc_reference_19frames.json",
    "reference_argmax.txt"
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

    $oldNames = ($copyFiles | ForEach-Object { "'$_'" }) -join " "
    $oldCheck = Invoke-BoardCommand -Port $port -Command "cd '$OldRemotePackage' && sha256sum $oldNames" -TimeoutSeconds 30
    if ($oldCheck.ExitCode -ne 0) { throw "Old verified package assets are unavailable" }

    $create = Invoke-BoardCommand -Port $port -Command "if [ -e '$RemotePackage' ]; then echo '__REMOTE_DIR_ALREADY_EXISTS__'; exit 73; else mkdir '$RemotePackage'; fi" -TimeoutSeconds 20
    if ($create.ExitCode -ne 0) { throw "Remote diagnostic directory is not new; stopped without deleting it" }

    $copyNames = ($copyFiles | ForEach-Object { "'$OldRemotePackage/$_'" }) -join " "
    $copy = Invoke-BoardCommand -Port $port -Command "cp $copyNames '$RemotePackage/'" -TimeoutSeconds 30
    if ($copy.ExitCode -ne 0) { throw "Failed to copy immutable board assets" }

    foreach ($name in $uploadFiles) {
        Send-BoardFile -Port $port -LocalPath (Join-Path $LocalPackage $name) -RemotePath "$RemotePackage/$name"
    }

    $verify = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && test ! -e run_all_frames.sh && sha256sum -c sha256_manifest.txt && chmod +x build_on_board.sh run_frame7.sh run_process_baseline.sh run_diagnostic.sh" -TimeoutSeconds 90
    if ($verify.ExitCode -ne 0) { throw "Board-package integrity gate failed" }

    Write-Host "`n=== BUILD ==="
    $build = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./build_on_board.sh && ls -l --time-style=full-iso build/npu_only_smoke build/npu_diag && sha256sum build/npu_only_smoke build/npu_diag" -TimeoutSeconds 360
    if ($build.ExitCode -ne 0) { throw "Board build failed" }

    Write-Host "`n=== FRAME 7 SANITY ==="
    $frame7 = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./run_frame7.sh" -TimeoutSeconds 180
    if ($frame7.ExitCode -ne 0 -or $frame7.Output -notmatch "V2_NPU_ONLY_SMOKE_REFERENCE_MATCH") { throw "Frame 7 sanity failed" }

    Write-Host "`n=== PROCESS-BOUNDARY BASELINE ==="
    $baseline = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./run_process_baseline.sh" -TimeoutSeconds 360
    if ($baseline.ExitCode -ne 0) { throw "Process-boundary baseline failed" }

    Write-Host "`n=== DIAGNOSTIC EXPERIMENTS 0-6 ==="
    $diag = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && ./run_diagnostic.sh" -TimeoutSeconds 900

    Write-Host "`n=== DIAGNOSTIC SUMMARIES ==="
    $summary = Invoke-BoardCommand -Port $port -Command "cd '$RemotePackage' && grep -hE '^(DIAG exp=|DIAG_RESULT=|DIAG_OBSERVE)' diag_logs/exp*.log 2>/dev/null || true" -TimeoutSeconds 60

    $sync = Invoke-BoardCommand -Port $port -Command "sync" -TimeoutSeconds 30
    if ($sync.ExitCode -ne 0) { throw "sync failed" }

    Write-Host "`nNPU_DIAGNOSTIC_BOARD_RUN_COMPLETE diag_script_rc=$($diag.ExitCode)"
} finally {
    if ($port.IsOpen) { $port.Close() }
}
