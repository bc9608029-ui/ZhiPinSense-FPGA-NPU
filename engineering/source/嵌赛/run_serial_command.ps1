param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string]$PortName = "COM12",
    [int]$BaudRate = 115200,
    [int]$WaitMilliseconds = 5000
)

$ErrorActionPreference = "Stop"

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
$port.WriteTimeout = 2000

try {
    $port.Open()
    $port.DiscardInBuffer()
    $port.WriteLine("")
    Start-Sleep -Milliseconds 400
    [void]$port.ReadExisting()
    $port.WriteLine($Command)

    $deadline = [DateTime]::UtcNow.AddMilliseconds($WaitMilliseconds)
    $builder = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $port.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$builder.Append($chunk)
        }
        Start-Sleep -Milliseconds 50
    }
    Write-Output $builder.ToString()
}
finally {
    if ($port.IsOpen) {
        $port.Close()
    }
    $port.Dispose()
}
