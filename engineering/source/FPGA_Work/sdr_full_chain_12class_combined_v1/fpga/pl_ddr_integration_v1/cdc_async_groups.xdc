# CDC async clock-group isolation for pl_ddr_mandatory_core_top_combined (smoke_v1).
#
# Root cause of the 9344 hold violations (WHS=-2.843, THS=-11389): the active
# constraint file carried no cross-domain isolation, so Vivado timed every path
# between the mutually-asynchronous clock domains as a "valid" inter-clock path.
# The failing hold paths are between GENERATED clocks:
#   clk_out1_clk_wiz_0        (100M, gen of clk_fpga_0)
#       <-> clk_pll_i_1        (200M, gen of pl_ddr_refclk via pll_clk3_out_1)
#   clk_out1_clk_wiz_core_50_1(50M,  gen of u_clk_wiz_core_50/inst/clk_in1)
#       <-> clk_pll_i_1        (200M)
#
# The RTL already carries the correct CDC structures, confirmed by report_cdc:
#   * u_engine handshake synchronizers (start_toggle -> request_sync1, 3-FF
#     with ASYNC_REG) and 2-FF completion/iq-base config synchronizers,
#   * NPU DDR-to-HP async FIFOs (U0_ddr2hp_itcn/u0_cdc_fifo_ddr_*, FIFO
#     Generator gconvfifo),
#   * fb_read_720p HP AXI (hp_clk) -> pixel (clk_74m25) async FIFO / level_cross.
#
# 组合设计(combined)相对原 NPU 基座的改动：frame_to_ps_largebuf 已被 fb_read_720p
# 取代，原第 5 组 frame_to_ps_inst0/cmos_clkgen_742_5_u0 的相机时钟生成 MMCM 不再
# 存在，故删除。新增的顶部单 MMCM u_mmcm_hdmi(100M gp_clk -> 74.25/371.25M) 输出
# clk_74m25/clk_371m25 是 clk_out1_clk_wiz_0(gp_clk) 的生成时钟，随 -include_generated_clocks
# clk_fpga_0 一并归入第 1 组，无需单列。
#
# 下面四个主时钟互异步（无共同源）。-include_generated_clocks 必需：Vivado 不把
# set_clock_groups -asynchronous 的组从主时钟自动传播到其生成时钟，须显式拉入每个
# 域整棵树。这是约束级改动：不改 RTL、不改位流。

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks clk_fpga_0] \
    -group [get_clocks -include_generated_clocks pl_ddr_refclk] \
    -group [get_clocks -include_generated_clocks u_clk_wiz_core_50/inst/clk_in1] \
    -group [get_clocks -include_generated_clocks jtag_clk]

# Round 03 CDC fix — restore the GP<->pixel-clock isolation that the official
# ai7030.xdc declared as set_false_path but whose hierarchy names
# (U0_ps_ai_peripheral / rx_sdi_inst) no longer match this design and are thus
# silently ignored.  In this combined design the single HDMI MMCM
# (u_mmcm_hdmi) derives clk_74m25 (pixel / cam_clk) from gp_clk
# (clk_out1_clk_wiz_0), so Vivado treats the two as RELATED and times the
# frame_ctrl (gp_clk) <-> display (cam_clk) crossing as a tiny 0.034 ns
# common-period path -> 324 setup failures (WNS -8.139).  Those 324 paths are
# all in frame_ctrl_u0 / u_vtc / u_fb_read_720p and are either (a) quasi-static
# display-timing config registers (H_SYNC/V_SYNC/... written once over AXI,
# read by the VTC) or (b) handshake/pulse synchronizers (bridge_s,
# pulse_cross_dvp_ov, level_cross) -- exactly the crossings the standalone
# hdmi_framebuffer_720p build cut with set_clock_groups -asynchronous.  Cutting
# the pair here (rather than via set_clock_groups, which warns for related
# generated clocks) restores that isolation.  Constraint-only: no RTL change,
# no re-synthesis.
set_false_path -from [get_clocks clk_out1_clk_wiz_0] -to [get_clocks clk_74m25]
set_false_path -from [get_clocks clk_74m25]        -to [get_clocks clk_out1_clk_wiz_0]
