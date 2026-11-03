@echo off
cd /d "F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga"
call "D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat" -mode batch -source "F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga\run_impl_cdc.tcl" -journal "F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga\run_impl_cdc.jou" -log "F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga\run_impl_cdc.log"
exit /b %ERRORLEVEL%
