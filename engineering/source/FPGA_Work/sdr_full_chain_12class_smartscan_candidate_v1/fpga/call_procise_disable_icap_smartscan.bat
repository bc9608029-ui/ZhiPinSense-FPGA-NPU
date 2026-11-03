@echo off
REM call_procise_disable_icap_smartscan.bat — apply FMSH increment_bit_cfg_v3 -disable_icap
REM to the smart-scan raw .bit.  Read-only on the candidate project outputs; never writes
REM Flash and never touches the frozen source project/bitstream.
set PROCISE_DIR=D:/fudanwei/Procise
set TCL_LIBRARY=%PROCISE_DIR%/tcl8.4
set PATH=%PROCISE_DIR%/dll;%PROCISE_DIR%/bin;%PATH%
set ICTIME_HOME=%PROCISE_DIR%
set APP_DIR=%PROCISE_DIR%
set FMSH_DB=%PROCISE_DIR%/db
procise.exe F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/m5_procise_disable_icap_smartscan.tcl
