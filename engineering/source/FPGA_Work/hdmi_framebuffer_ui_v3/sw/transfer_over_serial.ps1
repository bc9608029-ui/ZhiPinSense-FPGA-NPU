# transfer_over_serial.ps1 — send a file to the board over the UART console.
#
# The FMQL30TAI board has no usable network path, so PS binaries/scripts go over
# the serial console.  Two modes:
#
#   PASTE mode (default, safe):
#       Generates ONE self-contained shell command block and writes it to
#       <File>.serial.txt.  You then paste that block into your existing serial
#       console (minicom / PuTTY / MobaXterm).  This avoids two programs fighting
#       over the same COM port and lets you watch the transfer.  This is the
#       recommended mode.
#
#   SEND mode (-Send):
#       The script itself owns the COM port and drives the transfer.  Use this
#       ONLY when no interactive console is holding the port.  Data is paced in
#       small chunks with a delay so the board's UART/RX buffer is not overrun.
#
#   .\transfer_over_serial.ps1 -File phase2_ui_render -Dest /root/sw/phase2_ui_render
#   .\transfer_over_serial.ps1 -File phase2_ui_render -Dest /root/sw/phase2_ui_render -Send -Port COM12
#
# After the transfer the block runs `sha256sum` on the board and prints the hash;
# compare it to the value in SHA256SUMS.txt.

param(
    [string]$File = "",
    [string]$Dest = "",
    [Alias("Port")]
    [string]$PortName = "COM12",
    [int]$Baud = 115200,
    [switch]$Send,
    [int]$Chunk = 200,      # base64 chars per SEND chunk
    [int]$DelayMs = 10      # pause between SEND chunks
)

$ErrorActionPreference = "Stop"

if (-not $File) { Write-Host "usage: .\transfer_over_serial.ps1 -File <local> -Dest <board-path> [-Send] [-Port COM12] [-Baud 115200]"; exit 1 }
if (-not (Test-Path -LiteralPath $File)) { Write-Host "no such file: $File"; exit 1 }
if (-not $Dest) { Write-Host "missing -Dest (board destination path)"; exit 1 }

$full = (Resolve-Path -LiteralPath $File).Path
$name = Split-Path -Leaf $full
$bytes = [System.IO.File]::ReadAllBytes($full)
$b64 = [Convert]::ToBase64String($bytes)

# Split base64 into short lines (shell-safe, keeps each heredoc line tiny).
$lines = @()
for ($i = 0; $i -lt $b64.Length; $i += 76) {
    $lines += $b64.Substring($i, [Math]::Min(76, $b64.Length - $i))
}

$block = New-Object System.Text.StringBuilder
[void]$block.AppendLine("echo TRANSFER_BEGIN >&2")
[void]$block.AppendLine("cat > '$Dest'.b64 << 'TRANSFER_EOF'")
foreach ($ln in $lines) { [void]$block.AppendLine($ln) }
[void]$block.AppendLine("TRANSFER_EOF")
[void]$block.AppendLine("base64 -d '$Dest'.b64 > '$Dest' && rm -f '$Dest'.b64")
[void]$block.AppendLine("chmod +x '$Dest'")
[void]$block.AppendLine("echo TRANSFER_END >&2")
[void]$block.AppendLine("sha256sum '$Dest'")

if (-not $Send) {
    $out = "$full.serial.txt"
    [System.IO.File]::WriteAllText($out, $block.ToString(), [System.Text.Encoding]::ASCII)
    Write-Host "paste block written to: $out"
    Write-Host "  bytes: $($bytes.Length)  base64 chars: $($b64.Length)  lines: $($lines.Count)"
    Write-Host "  dest on board: $Dest"
    Write-Host "Paste the file contents into your serial console (at a shell prompt)."
    Write-Host "Compare the printed sha256 to SHA256SUMS.txt."
    exit 0
}

# ---- SEND mode: drive the COM port directly ----
$serial = [System.IO.Ports.SerialPort]::new(
    $PortName,
    $Baud,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$serial.ReadTimeout = 1500
$serial.WriteTimeout = 2000
$serial.NewLine = "`r`n"

try {
    $serial.Open()
} catch {
    Write-Host "cannot open $PortName (is another console holding it?): $($_.Exception.Message)"
    exit 2
}

Write-Host "opened $PortName @ $Baud; sending in $($lines.Count) chunks ($DelayMs ms pause)..."

$header = "cat > '$Dest'.b64 << 'TRANSFER_EOF'`r"
$serial.Write($header)
Start-Sleep -Milliseconds 200

foreach ($ln in $lines) {
    $serial.Write($ln + "`r")
    Start-Sleep -Milliseconds $DelayMs
}

$serial.Write("TRANSFER_EOF`r")
Start-Sleep -Milliseconds 200
$serial.Write("base64 -d '$Dest'.b64 > '$Dest' && rm -f '$Dest'.b64`r")
$serial.Write("chmod +x '$Dest'`r")
$serial.Write("sha256sum '$Dest'`r")

Write-Host "sent. waiting for board's sha256 output (up to ~10 s)..."
$deadline = [DateTime]::Now.AddSeconds(10)
$got = New-Object System.Text.StringBuilder
while ([DateTime]::Now -lt $deadline) {
    try {
        $n = $serial.BytesToRead
        if ($n -gt 0) {
            $buf = New-Object byte[] $n
            [void]$serial.Read($buf, 0, $n)
            [void]$got.Append([System.Text.Encoding]::ASCII.GetString($buf))
        }
    } catch { break }
    Start-Sleep -Milliseconds 100
}
Write-Host "board output:"
Write-Host $got.ToString()

$serial.Close()
Write-Host "done. compare the board's sha256 to SHA256SUMS.txt."
