# hdmi_framebuffer_720p.xdc — constraints for the Phase 1A framebuffer top.
#
# Pin / IOSTANDARD / clock values are copied verbatim from the proven colorbar
# constraints (hdmi_board_bringup_v1/fpga/constrs/hdmi_colorbar_720p.xdc), which
# in turn were copied from the official demo (fpai_demo_fpga/constrs_1/).
#
# Only the ports present on hdmi_framebuffer_720p_top are constrained:
#   sys_clk_p/n, sys_rst, led[1:0], HDMI_CLK_P, HDMI_TX_P[2:0].
# DDR_* and FIXED_IO_* pins are auto-constrained by the PS7 IP (ps_ai.bd), so
# they are deliberately NOT listed here.

#####################  hdmi (PL TMDS)  #####################################
# _P pins + IOSTANDARD are official; the *_N pins are the differential partners
# and Vivado auto-places them from these _P LOCs (the official XDC constrains
# only the _P pins the same way).
set_property PACKAGE_PIN AC17 [get_ports HDMI_CLK_P]
set_property PACKAGE_PIN AA15 [get_ports {HDMI_TX_P[0]}]
set_property PACKAGE_PIN Y16  [get_ports {HDMI_TX_P[1]}]
set_property PACKAGE_PIN W16  [get_ports {HDMI_TX_P[2]}]
set_property IOSTANDARD TMDS_33 [get_ports HDMI_CLK_P]
set_property IOSTANDARD TMDS_33 [get_ports {HDMI_TX_P[*]}]
#####################  hdmi  ################################################

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

#####################  CDC (cross-clock-domain)  ############################
# gp_clk = clk_out1_clk_wiz_0 (PS7 FCLK_CLK0 -> clk_wiz_0) is asynchronous to the
# crystal-derived display clocks (clk_74m25 pixel clock, clk_100m hp_clk).  These
# are different clock sources: PS7 PLL vs the 200 MHz board oscillator through
# independent MMCMs.  Every crossing is synchronized in RTL — frame_ctrl uses
# pulse_cross_camera/bridge_s/level_cross, and the fb read path uses level_cross
# + async FIFOs — so the boundaries are declared asynchronous.  This is the same
# treatment the official design applies in ai7030.xdc (set_false_path between the
# PS7 clk_wiz output and the camera/display clocks).
set_clock_groups -asynchronous \
    -group [get_clocks clk_out1_clk_wiz_0] \
    -group [get_clocks clk_74m25] \
    -group [get_clocks clk_100m]

# Async reset button: synchronized in RTL (mirrors official ai7030.xdc line 8).
set_false_path -from [get_ports sys_rst]
# Status LEDs are not timing-critical (mirrors official ai7030.xdc lines 9-10).
set_false_path -to [get_ports {led[0]}]
set_false_path -to [get_ports {led[1]}]
