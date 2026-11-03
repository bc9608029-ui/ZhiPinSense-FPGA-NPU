@echo off
cd /d F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga
D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat -mode batch -source run_bitstream_generate.tcl -log reports\pl_ddr_mandatory_core_v1\bitstream_generate.log -journal reports\pl_ddr_mandatory_core_v1\bitstream_generate.jou
set VIVADO_EXIT=%ERRORLEVEL%
echo VIVADO_BATCH_EXIT_CODE=%VIVADO_EXIT%
exit /b %VIVADO_EXIT%
