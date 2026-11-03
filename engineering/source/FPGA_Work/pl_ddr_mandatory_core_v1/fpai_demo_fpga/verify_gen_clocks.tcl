# Verify `get_clocks -include_generated_clocks` gathers every generated clock
# under its primary domain (recursively), BEFORE re-running implementation.
# Read-only: opens the placed.dcp, no run, no bitstream, no RTL touched.

set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_placed.dcp}
open_checkpoint $dcp

puts "=== B. -include_generated_clocks on each primary domain ==="
foreach p [list clk_fpga_0 pl_ddr_refclk u_clk_wiz_core_50/inst/clk_in1 jtag_clk \
                 u_ps_ai_peripheral/frame_to_ps_inst0/cmos_clkgen_742_5_u0/inst/clk_in1] {
    set all [get_clocks -quiet -include_generated_clocks $p]
    puts "  DOMAIN $p => count=[llength $all]"
    foreach c $all { puts "      [get_property NAME $c]" }
}

puts "VERIFY_GEN_CLOCKS_DONE"
close_design
