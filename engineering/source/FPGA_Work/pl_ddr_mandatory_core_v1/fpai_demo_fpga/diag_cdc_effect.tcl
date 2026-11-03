# Diagnose WHY the set_clock_groups -asynchronous did not remove the hold
# violations.  Opens the FRESH placed.dcp from this run (which had
# cdc_async_groups.xdc parsed during opt_design) and reports:
#   1. every clock (primary + generated) with its master/source,
#   2. the hold + setup clock-interaction matrix (Ignored vs Timed (unsafe)),
#   3. the worst hold paths with their From/To clocks.
# Read-only: no run launched, no bitstream, no RTL touched.

set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_placed.dcp}
set outdir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/reports/pl_ddr_mandatory_core_v1/diag_cdc_effect}
file mkdir $outdir

open_checkpoint $dcp

puts "=== 1. ALL CLOCKS (name | period | generated | master-pin) ==="
foreach c [get_clocks] {
    set nm  [get_property NAME $c]
    set per [get_property PERIOD $c]
    set gen [get_property IS_GENERATED $c]
    set src [get_property SOURCE_PINS $c]
    puts "  $nm | period=$per | generated=$gen | master=$src"
}

puts "=== 2. clock interaction (min/hold + max/setup) ==="
report_clock_interaction -delay_type min -file [file join $outdir clock_interaction_hold.rpt]
report_clock_interaction -delay_type max -file [file join $outdir clock_interaction_setup.rpt]

puts "=== 3. worst hold paths (From/To clocks) ==="
report_timing -delay_type min -max_paths 20 -nworst 2 -file [file join $outdir worst_hold_paths.rpt]

puts "=== 4. key generated-clock name resolution ==="
foreach n [list clk_out1_clk_wiz_0 clk_pll_i_1 clk_out1_clk_wiz_core_50_1 \
                 clk_out1_AI_CORE_CLK_ST_1 cam_clk_use_742_5] {
    set clks [get_clocks -quiet $n]
    puts "  get_clocks '$n' => count=[llength $clks]  [join $clks {, }]"
}

puts "DIAG_CDC_EFFECT_DONE"
close_design
