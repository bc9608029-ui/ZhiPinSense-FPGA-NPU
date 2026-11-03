$ErrorActionPreference='Stop'
$env:PYTHONPATH='E:\FPGA_Work\rml24_tx_console_integration_20261031\deps;'+$env:PYTHONPATH
$env:QT_QPA_FONTDIR='C:\Windows\Fonts'
& 'D:\Miniconda3\python.exe' (Join-Path $PSScriptRoot 'app.py')
