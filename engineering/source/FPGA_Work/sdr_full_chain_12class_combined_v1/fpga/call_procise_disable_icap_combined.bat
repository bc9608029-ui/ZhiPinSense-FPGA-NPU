@echo off
REM call_procise_disable_icap_combined.bat — 对合并 raw .bit 应用 FMSH increment_bit_cfg_v3 -disable_icap。
REM 仅读取合并工程内产物，绝不写 Flash、绝不触碰来源工程。
set PROCISE_DIR=D:/fudanwei/Procise
set TCL_LIBRARY=%PROCISE_DIR%/tcl8.4
set PATH=%PROCISE_DIR%/dll;%PROCISE_DIR%/bin;%PATH%
set ICTIME_HOME=%PROCISE_DIR%
set APP_DIR=%PROCISE_DIR%
set FMSH_DB=%PROCISE_DIR%/db
procise.exe F:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/m5_procise_disable_icap_combined.tcl
