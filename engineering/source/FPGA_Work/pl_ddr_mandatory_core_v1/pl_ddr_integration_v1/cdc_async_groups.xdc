# CDC async clock-group isolation for pl_ddr_mandatory_core_top.
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
#     Generator gconvfifo).
#
# The five primary clocks below are mutually asynchronous (no common source).
# -include_generated_clocks is REQUIRED: Vivado does not propagate a
# set_clock_groups -asynchronous group from a primary clock to its generated
# clocks automatically, so the group must explicitly pull in the whole clock
# tree of each domain.  This is a constraint-level change only: no RTL
# modification, no bitstream.

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks clk_fpga_0] \
    -group [get_clocks -include_generated_clocks pl_ddr_refclk] \
    -group [get_clocks -include_generated_clocks u_clk_wiz_core_50/inst/clk_in1] \
    -group [get_clocks -include_generated_clocks jtag_clk] \
    -group [get_clocks -include_generated_clocks u_ps_ai_peripheral/frame_to_ps_inst0/cmos_clkgen_742_5_u0/inst/clk_in1]
