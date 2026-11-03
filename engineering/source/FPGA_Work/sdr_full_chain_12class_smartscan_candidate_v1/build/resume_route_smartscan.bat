@echo off
rem resume_route_smartscan.bat — 续跑 m4 布线（placed 检查点 -> route -> bitgen），守护式启动。
rem 由 Windows 计划任务调用，脱离 Claude Code 会话独立运行，会话结束不会被杀。

setlocal
set "FMSH_PROCISE_PATH=D:\fudanwei\Procise"
set "VIVADO=D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat"
set "TCL=F:\FPGA_Work\sdr_full_chain_12class_smartscan_candidate_v1\fpga\m4c_resume_route_smartscan.tcl"
set "JOU=F:\FPGA_Work\sdr_full_chain_12class_smartscan_candidate_v1\build\m4c_resume_route_smartscan.jou"
set "LOG=F:\FPGA_Work\sdr_full_chain_12class_smartscan_candidate_v1\build\m4c_resume_route_smartscan.log"
set "RC=F:\FPGA_Work\sdr_full_chain_12class_smartscan_candidate_v1\build\m4c_resume_route_smartscan.rc"

echo === M4C_START %DATE% %TIME% ===
call "%VIVADO%" -mode batch -notrace -source "%TCL%" -journal "%JOU%" -log "%LOG%"
set "EC=%ERRORLEVEL%"
echo M4C_DONE_RC=%EC% %DATE% %TIME% > "%RC%"
echo === M4C_END %DATE% %TIME% rc=%EC% ===
exit /b %EC%
