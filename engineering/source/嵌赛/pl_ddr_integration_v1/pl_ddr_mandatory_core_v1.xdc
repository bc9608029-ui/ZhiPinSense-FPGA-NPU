# FMQL30TAI Lite pins retained from the official fpai_demo constraints.
# The PS fixed I/O and both DDR interfaces are constrained by their official
# block-design/MIG files.  This file only covers remaining board-level ports.

set_property PACKAGE_PIN F8 [get_ports sys_rst]
set_property IOSTANDARD LVCMOS15 [get_ports sys_rst]
set_false_path -from [get_ports sys_rst]

create_clock -period 5.000 -name pl_ddr_refclk [get_ports sys_clk_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports sys_clk_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports sys_clk_n]
set_property PACKAGE_PIN C8 [get_ports sys_clk_p]
set_property PACKAGE_PIN C7 [get_ports sys_clk_n]

set_property PACKAGE_PIN J1 [get_ports {led[0]}]
set_property PACKAGE_PIN M6 [get_ports {led[1]}]
set_property IOSTANDARD LVCMOS15 [get_ports {led[*]}]
set_false_path -to [get_ports {led[*]}]

set_property PACKAGE_PIN AC17 [get_ports HDMI_CLK_P]
set_property PACKAGE_PIN AA15 [get_ports {HDMI_TX_P[0]}]
set_property PACKAGE_PIN Y16 [get_ports {HDMI_TX_P[1]}]
set_property PACKAGE_PIN W16 [get_ports {HDMI_TX_P[2]}]
set_property IOSTANDARD TMDS_33 [get_ports HDMI_CLK_P]
set_property IOSTANDARD TMDS_33 [get_ports {HDMI_TX_P[*]}]

set_property PACKAGE_PIN AD16 [get_ports PJTAG_TDO]
set_property PACKAGE_PIN AB14 [get_ports PJTAG_TMS]
set_property PACKAGE_PIN AB15 [get_ports PJTAG_TCK]
set_property PACKAGE_PIN AD15 [get_ports PJTAG_TDI]
set_property IOSTANDARD LVCMOS33 [get_ports {PJTAG_TCK PJTAG_TMS PJTAG_TDI PJTAG_TDO}]
set_property PULLUP true [get_ports PJTAG_TDO]
create_clock -period 20.000 -name jtag_clk -waveform {0.000 10.000} [get_ports PJTAG_TCK]

# Official placement required by the FMQL30TAI AI clocking shell.
set_property LOC PLLE2_ADV_X1Y3 [get_cells u_ps_ai_peripheral/ZGolo/u_AI_Mate_top/clkrst_wrapper_u0/AI_CORE_CLK/inst/plle2_adv_inst]
