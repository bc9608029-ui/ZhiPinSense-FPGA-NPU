# Read-only verification of the new CDC set_clock_groups constraint BEFORE any
# re-run: open the placed DCP, list every primary clock, confirm each name in
# cdc_async_groups.xdc resolves, apply the constraint, and re-report the clock
# interaction matrix so the async pairs must show "Ignored" instead of "Timed
# (unsafe)".  No run is launched, no bitstream is produced.

set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_placed.dcp}
set xdc {F:/FPGA_Work/pl_ddr_mandatory_core_v1/pl_ddr_integration_v1/cdc_async_groups.xdc}
set outdir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/reports/pl_ddr_mandatory_core_v1/diag_placed}
file mkdir $outdir

open_checkpoint $dcp

puts "=== 1. ALL PRIMARY CLOCKS (IS_GENERATED == false) ==="
foreach c [get_clocks -filter {IS_GENERATED == false}] {
    puts "  PRIMARY: [get_property NAME $c]  period=[get_property PERIOD $c]"
}

puts "=== 2. NAME RESOLUTION CHECK for cdc_async_groups.xdc ==="
foreach n [list clk_fpga_0 pl_ddr_refclk jtag_clk \
                 u_clk_wiz_core_50/inst/clk_in1 \
                 u_ps_ai_peripheral/frame_to_ps_inst0/cmos_clkgen_742_5_u0/inst/clk_in1] {
    set clks [get_clocks -quiet $n]
    puts "  get_clocks '$n' => count=[llength $clks]  [join $clks {, }]"
}

puts "=== 3. apply the new constraint and re-report clock interaction (hold) ==="
read_xdc $xdc
report_clock_interaction -delay_type min -file [file join $outdir clock_interaction_hold_after_cdc.rpt]

puts "VERIFY_CDC_GROUPS_DONE"
close_design
