# hdmi_colorbar_720p.xdc — constraints for the standalone 720p colorbar test.
# Pin/IOSTANDARD/clock values are copied verbatim from the official demo
# constraints (fpai_demo_fpga/constrs_1/impl_constraints.xdc); only the ports
# relevant to hdmi_colorbar_720p_top are listed.  This is a NEW file.

#####################  hdmi (PL "IO模" TMDS)  ############################
# _P pins + IOSTANDARD are official; the *_N pins are the differential partners
# and Vivado auto-places them from these _P LOCs (the official XDC constrains
# only the _P pins the same way).
set_property PACKAGE_PIN AC17 [get_ports HDMI_CLK_P]
set_property PACKAGE_PIN AA15 [get_ports {HDMI_TX_P[0]}]
set_property PACKAGE_PIN Y16  [get_ports {HDMI_TX_P[1]}]
set_property PACKAGE_PIN W16  [get_ports {HDMI_TX_P[2]}]
set_property IOSTANDARD TMDS_33 [get_ports HDMI_CLK_P]
set_property IOSTANDARD TMDS_33 [get_ports {HDMI_TX_P[*]}]
#####################  hdmi  ############################################

# system reset (active high)
set_property PACKAGE_PIN F8 [get_ports sys_rst]
set_property IOSTANDARD LVCMOS15 [get_ports sys_rst]

# status LEDs (BANK13)
set_property PACKAGE_PIN J1 [get_ports {led[0]}]
set_property IOSTANDARD LVCMOS15 [get_ports {led[0]}]
set_property PACKAGE_PIN M6 [get_ports {led[1]}]
set_property IOSTANDARD LVCMOS15 [get_ports {led[1]}]

# 200 MHz system clock (PL reference oscillator)
set_property PACKAGE_PIN C8 [get_ports sys_clk_p]
set_property PACKAGE_PIN C7 [get_ports sys_clk_n]
set_property IOSTANDARD DIFF_SSTL15 [get_ports sys_clk_p]
set_property IOSTANDARD DIFF_SSTL15 [get_ports sys_clk_n]
create_clock -period 5.000 [get_ports sys_clk_p]
