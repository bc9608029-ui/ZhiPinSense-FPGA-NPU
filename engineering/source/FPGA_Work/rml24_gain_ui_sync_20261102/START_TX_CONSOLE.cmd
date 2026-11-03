@echo off
set "PYTHONPATH=E:\FPGA_Work\rml24_tx_console_integration_20261031\deps;%PYTHONPATH%"
set "QT_QPA_FONTDIR=C:\Windows\Fonts"
"D:\Miniconda3\python.exe" "%~dp0pc_console\app.py" %*
