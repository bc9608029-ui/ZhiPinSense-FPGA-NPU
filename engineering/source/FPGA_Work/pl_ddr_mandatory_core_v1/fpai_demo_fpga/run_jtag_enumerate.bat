@echo off
cd /d F:\FPGA_Work\pl_ddr_mandatory_core_v1\fpai_demo_fpga
D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat -mode batch -source enumerate_pl_jtag_v2.tcl -log reports\pl_ddr_mandatory_core_v1\jtag_enumerate.log -journal reports\pl_ddr_mandatory_core_v1\jtag_enumerate.jou
set VIVADO_EXIT=%ERRORLEVEL%
echo VIVADO_JTAG_ENUM_EXIT_CODE=%VIVADO_EXIT%
exit /b %VIVADO_EXIT%
