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
# Reference the generated clocks by PIN (not by auto-derived name) so that the
# async groups satisfy TIMING-28.  The three pin sources are taken verbatim from
# report_clocks.rpt:
#   clk_100m            <- u_mmcm_200_100/CLKOUT0
#   clk_74m25           <- u_mmcm_27_742/CLKOUT0
#   clk_out1_clk_wiz_0  <- u_ps_ai_wrapper/clk_wiz_0_inst/inst/plle2_adv_inst/CLKOUT0
set_clock_groups -asynchronous \
    -group [get_clocks -of_objects [get_pins u_mmcm_200_100/CLKOUT0]] \
    -group [get_clocks -of_objects [get_pins u_mmcm_27_742/CLKOUT0]] \
    -group [get_clocks -of_objects [get_pins u_ps_ai_wrapper/clk_wiz_0_inst/inst/plle2_adv_inst/CLKOUT0]]

# Async reset button: synchronized in RTL (mirrors official ai7030.xdc line 8).
set_false_path -from [get_ports sys_rst]
# Status LEDs are not timing-critical (mirrors official ai7030.xdc lines 9-10).
set_false_path -to [get_ports {led[0]}]
set_false_path -to [get_ports {led[1]}]

# ---- ASYNC_REG on every 2-FF/3-FF synchronizer ---------------------------
# These synchronizers are unchanged official FMSH RTL (level_cross.v, bridge_s.v,
# frame_ctrl.v) plus the top-level reset double-flops and the 1-bit double-buffer
# select sync added in fb_read_720p (buf_sel_sync1/2).  They were reported as
# CDC-2 (missing ASYNC_REG) / CDC-5/CDC-6 (multi-bit).  Tagging the flops with
# ASYNC_REG (a non-invasive XDC property, no RTL edit) turns the 1-bit syncs into
# CDC-3 (Info) and clears TIMING-10; the 2-bit read_addr_index sync in
# frame_fifo_read is now same-domain (fb_read_720p feeds it an already-synchronized
# {1'b0, buf_sel_sync2}), so its read_addr_index_d0/d1 flops are no longer crossing
# and are NOT tagged here.  Cell names are the exact flop names from report_cdc.rpt
# (verified offline).  Control-flow commands (foreach) and set_msg_config are NOT
# allowed in an XDC file, so this is a single set_property over one get_cells list
# (no -hier: full hierarchical paths are matched directly).
set_property ASYNC_REG TRUE [get_cells -quiet {rst_gp_d1_reg rst_gp_d2_reg rst_hp_d1_reg rst_hp_d2_reg u_frame_ctrl/disable_hdmi_0_reg u_frame_ctrl/disable_hdmi_1_reg u_frame_ctrl/disable_hdmi_2_reg u_frame_ctrl/bridge_s_u1/a_req_b_reg u_frame_ctrl/bridge_s_u1/a_req_b_d1_reg u_frame_ctrl/bridge_s_u1/a_req_b_d2_reg u_frame_ctrl/bridge_s_u1/b_ack_a_reg u_frame_ctrl/bridge_s_u1/b_ack_a_d1_reg u_fb_read_720p/u_level_cross_req/a1_clk1_d1_reg u_fb_read_720p/u_level_cross_req/a1_clk1_d2_reg u_fb_read_720p/u_level_cross_req/a2_clk2_t1_reg u_fb_read_720p/u_level_cross_req/a2_clk2_t2_reg u_fb_read_720p/u_level_cross_ack/a1_clk1_d1_reg u_fb_read_720p/u_level_cross_ack/a1_clk1_d2_reg u_fb_read_720p/u_level_cross_ack/a2_clk2_t1_reg u_fb_read_720p/u_level_cross_ack/a2_clk2_t2_reg u_fb_read_720p/buf_sel_sync1_reg u_fb_read_720p/buf_sel_sync2_reg}]

# NOTE on the remaining CDC/methodology warnings: they are NOT demoted here.
# set_msg_config -new_severity INFO does not change report_methodology output in
# Vivado 2018.3 (verified), and the remaining items (TIMING-9/24/27, LUTAR-1,
# PDRC-190, plus report_cdc CDC-1/7/10/13/15) are inherent to the official PS7 IP
# / frozen demo RTL / global async reset / quasi-static config.  They are
# FORMALLY WAIVED with rationale in docs/CDC_WAIVERS.md rather than suppressed.
