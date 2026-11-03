@echo off
REM call_procise_disable_icap.bat — Phase 1B/1C/2/3: produce *_disable_icap.bit with Procise.
REM Mirrors ps_pl_ctrl_smoke_resetfix/call_procise_disable_icap.bat (same Procise dir/env).
REM Run this AFTER build_phase1b.tcl has produced hdmi_framebuffer_720p_top.bit.
@set PROCISE_DIR=D:/fudanwei/Procise
@set TCL_LIBRARY=%PROCISE_DIR%/tcl8.4
@set PATH=%PROCISE_DIR%/dll;%PROCISE_DIR%/bin;%PATH%
@set ICTIME_HOME=%PROCISE_DIR%
@set APP_DIR=%PROCISE_DIR%
@set FMSH_DB=%PROCISE_DIR%/db
@procise.exe F:/FPGA_Work/hdmi_framebuffer_ui_v2/fpga/procise_run_disable_icap.tcl
