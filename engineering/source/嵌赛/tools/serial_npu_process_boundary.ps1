param(
    [string]$PortName = "COM12",
    [string]$RemotePackage = "/home/work/npu_stage_v1"
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
        [int]$TimeoutSeconds = 300
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
            Write-Host -NoNewline $chunk
            $match = [regex]::Match($text.ToString(), [regex]::Escape($marker) + ":([0-9]+)")
            if ($match.Success) {
                return [pscustomobject]@{ ExitCode = [int]$match.Groups[1].Value; Output = $text.ToString() }
            }
        }
        Start-Sleep -Milliseconds 20
    }
    throw "Timed out after $TimeoutSeconds seconds"
}

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

    $command = @"
cd '$RemotePackage' && passed=0 && failed=0 && for frame in `$(seq 7 18); do log="/tmp/npu_frame_`$frame.log"; ./build/npu_only_smoke --model model.json --raw model.raw --tensor expected_tensor_plddr.bin --frame "`$frame" --reference reference_argmax.txt >"`$log" 2>&1; rc=`$?; grep -E '^(frame=|  reference_argmax=|processed_frames=|forward_time:|setup_time:|class_match=|V2_NPU_ONLY_)' "`$log"; if [ "`$rc" -eq 0 ] && grep -q '^V2_NPU_ONLY_SMOKE_REFERENCE_MATCH`$' "`$log"; then passed=`$((passed+1)); else failed=`$((failed+1)); fi; done; echo "__PROCESS_BOUNDARY_SUMMARY__=passed:`$passed,failed:`$failed"; test "`$passed" -eq 12 && test "`$failed" -eq 0
"@.Trim()

    $result = Invoke-BoardCommand -Port $port -Command $command -TimeoutSeconds 300
    if ($result.ExitCode -ne 0 -or $result.Output -notmatch "__PROCESS_BOUNDARY_SUMMARY__=passed:12,failed:0") {
        throw "Process-boundary NPU validation failed"
    }

    $sync = Invoke-BoardCommand -Port $port -Command "sync" -TimeoutSeconds 30
    if ($sync.ExitCode -ne 0) { throw "sync failed" }
    Write-Host "`nNPU_PROCESS_BOUNDARY_RETEST_PASS"
} finally {
    if ($port.IsOpen) { $port.Close() }
}
