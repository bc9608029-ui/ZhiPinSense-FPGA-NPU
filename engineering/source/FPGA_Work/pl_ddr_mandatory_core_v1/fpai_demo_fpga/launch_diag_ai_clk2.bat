@echo off
cd /d "F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga"
call "D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat" -mode batch -source "F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga\diag_ai_clk2.tcl" -journal "F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga\diag_ai_clk2.jou" -log "F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga\diag_ai_clk2.log"
exit /b %ERRORLEVEL%
