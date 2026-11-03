param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string]$Port = "COM12",
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 20
)

$serial = [System.IO.Ports.SerialPort]::new(
    $Port,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.ReadTimeout = 200
$serial.WriteTimeout = 2000
$token = "__CODEX_$([Guid]::NewGuid().ToString('N'))__"
$wrapped = ('{0}; __codex_rc=$?; printf ''\n{1}:%s\n'' "$__codex_rc"' -f $Command, $token)

try {
    $serial.Open()
    Start-Sleep -Milliseconds 250
    $serial.DiscardInBuffer()
    $serial.Write("`r`n")
    Start-Sleep -Milliseconds 200
    $null = $serial.ReadExisting()
    $serial.Write($wrapped + "`r`n")

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $output = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $chunk = $serial.ReadExisting()
            if ($chunk.Length -gt 0) {
                $null = $output.Append($chunk)
                if ($output.ToString() -match "(?m)^$([regex]::Escape($token)):(True|False|0|1)\r?$") {
                    break
                }
            }
        }
        catch [System.TimeoutException] {
        }
        Start-Sleep -Milliseconds 50
    }

    $text = $output.ToString()
    if ($text -notmatch "(?m)^$([regex]::Escape($token)):(True|False|0|1)\r?$") {
        throw "Timed out waiting for command completion marker. Partial output:`n$text"
    }
    $text -replace "(?m)^$([regex]::Escape($token)):(True|False|0|1)\r?\n?", ""
}
finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
}
