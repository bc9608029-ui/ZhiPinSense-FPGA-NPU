param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string]$PortName = "COM12",
    [int]$BaudRate = 115200,
    [int]$WaitMilliseconds = 5000
)

$ErrorActionPreference = "Stop"

function Read-SerialFor {
    param(
        [System.IO.Ports.SerialPort]$Port,
        [int]$Milliseconds
    )

    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $builder = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        $chunk = $Port.ReadExisting()
        if ($chunk.Length -gt 0) {
            [void]$builder.Append($chunk)
        }
        Start-Sleep -Milliseconds 50
    }
    return $builder.ToString()
}

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
    $prompt = Read-SerialFor -Port $port -Milliseconds 800
    if ($prompt -notmatch '(?m)[#$]\s*$') {
        throw "No Linux shell prompt was detected on $PortName. Serial output: $prompt"
    }

    $marker = "__CODEX_SERIAL_DONE__"
    $port.WriteLine("$Command; printf '\n${marker}:%s\n' `$?")
    $result = Read-SerialFor -Port $port -Milliseconds $WaitMilliseconds
    Write-Output $result
    if ($result -notmatch [regex]::Escape($marker)) {
        throw "Command completion marker was not returned within $WaitMilliseconds ms"
    }
} finally {
    if ($port.IsOpen) {
        $port.Close()
    }
    $port.Dispose()
}
