param(
    [string]$PortName = "COM12",
    [int]$BaudRate = 115200,
    [string]$LoginName = "root",
    [string]$LoginPassword = "fmsh"
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

$linuxCommand = 'PYTHONPATH=/usr/lib/aarch64-linux-gnu /usr/bin/python3 -c ''import xrt,time; b=0x400c0000; d=xrt.Device.Open("axi://zg330aiu?npu=0x40000000&dma=0x80000000"); r=d.defaultRegRegion(); v=r.read(b,False); print("VERSION=0x%08x"%v); assert v==0x20260927; r.write(b+4,0x12345678,False); s=r.read(b+4,False); print("SCRATCH=0x%08x"%s); assert s==0x12345678; n0=r.read(b+16,False); r.write(b+8,1,False); time.sleep(0.01); st=r.read(b+12,False); n1=r.read(b+16,False); print("STATUS=0x%x RUN_COUNT_BEFORE=%d RUN_COUNT_AFTER=%d"%(st,n0,n1)); assert (st&2)!=0 and (st&1)==0 and n1==n0+1; xrt.Device.Close(d); print("PS_PL_CTRL_SMOKE_LINUX_PASS")'''

$port = [System.IO.Ports.SerialPort]::new($PortName, $BaudRate, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$port.Handshake = [System.IO.Ports.Handshake]::None
$port.NewLine = "`n"
$port.ReadTimeout = 250
$port.WriteTimeout = 2000

try {
    $port.Open()
    $port.DiscardInBuffer()
    $port.WriteLine("")
    $text = Read-SerialFor -Port $port -Milliseconds 1500

    if ($text -match '(?i)login:\s*$') {
        $port.WriteLine($LoginName)
        $text += Read-SerialFor -Port $port -Milliseconds 1000
    }
    if ($text -match '(?i)Password:\s*$') {
        $port.WriteLine($LoginPassword)
        $text += Read-SerialFor -Port $port -Milliseconds 1800
    }

    if ($text -notmatch '(?m)[#$]\s*$') {
        throw "No Linux shell prompt was detected on $PortName. Serial output: $text"
    }

    $port.WriteLine($linuxCommand)
    $result = Read-SerialFor -Port $port -Milliseconds 15000
    Write-Output $result
    if ($result -notmatch 'PS_PL_CTRL_SMOKE_LINUX_PASS') {
        throw "Smoke PASS marker was not returned"
    }
} finally {
    if ($port.IsOpen) {
        $port.Close()
    }
    $port.Dispose()
}
