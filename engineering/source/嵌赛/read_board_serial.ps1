param(
    [string]$PortName = "COM12",
    [int]$BaudRate = 115200,
    [int]$Milliseconds = 20000
)

$ErrorActionPreference = "Stop"
$port = [System.IO.Ports.SerialPort]::new($PortName, $BaudRate, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$port.Handshake = [System.IO.Ports.Handshake]::None
try {
    $port.Open()
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $builder = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $port.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$builder.Append($chunk)
        }
        Start-Sleep -Milliseconds 50
    }
    Write-Output $builder.ToString()
} finally {
    if ($port.IsOpen) {
        $port.Close()
    }
    $port.Dispose()
}
