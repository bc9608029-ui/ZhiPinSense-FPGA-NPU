# Diagnostic (read-only) pass over the PLACED design.  Route was aborted at
# Phase 4.2 due to congestion; place_design completed cleanly, so this script
# opens the placed DCP and emits timing / clock-interaction / CDC / check_timing
# / congestion reports to pin down (a) the huge hold violation and (b) the
# congestion hotspots.  It does NOT touch any XDC, does NOT add constraints,
# does NOT reset/launch any run, and does NOT produce a bitstream.

set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_placed.dcp}
set outdir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/reports/pl_ddr_mandatory_core_v1/diag_placed}
file mkdir $outdir

open_checkpoint $dcp

# 1. Worst setup / hold paths, full clock + hierarchy expansion.
report_timing_summary -delay_type max -path_type full_clock_expanded -max_paths 20 -nworst 1 -file [file join $outdir setup_timing_summary.rpt]
report_timing_summary -delay_type min -path_type full_clock_expanded -max_paths 20 -nworst 1 -file [file join $outdir hold_timing_summary.rpt]

# 2. Clock interaction matrices (setup + hold).
report_clock_interaction -delay_type max -file [file join $outdir clock_interaction_setup.rpt]
report_clock_interaction -delay_type min -file [file join $outdir clock_interaction_hold.rpt]

# 3. CDC report with details.
report_cdc -details -file [file join $outdir cdc_details.rpt]

# 4. Constraint completeness / issues.
check_timing -verbose -file [file join $outdir check_timing.rpt]

# 5. Congestion (2018.3 command equivalent of report_design_analysis -congestion).
report_congestion -greedy -hotspots -max_routing_hotspots 20 -file [file join $outdir congestion.rpt]

# 6. Hierarchical utilization to correlate hotspots to module hierarchy.
report_utilization -hierarchical -file [file join $outdir utilization_hier.rpt]

# Machine-readable worst-path summary (slack + endpoints).
set gate_ch [open [file join $outdir worst_paths.txt] w]
puts $gate_ch "=== WORST SETUP (max) ==="
foreach p [get_timing_paths -delay_type max -max_paths 10 -nworst 1] {
    set sp [get_property STARTPOINT_PIN $p]
    set ep [get_property ENDPOINT_PIN $p]
    set sl [get_property SLACK $p]
    set grp [get_property GROUPS $p]
    puts $gate_ch "SLACK=$sl  START=$sp  END=$ep  CLOCKS=$grp"
}
puts $gate_ch "=== WORST HOLD (min) ==="
foreach p [get_timing_paths -delay_type min -max_paths 10 -nworst 1] {
    set sp [get_property STARTPOINT_PIN $p]
    set ep [get_property ENDPOINT_PIN $p]
    set sl [get_property SLACK $p]
    set grp [get_property GROUPS $p]
    puts $gate_ch "SLACK=$sl  START=$sp  END=$ep  CLOCKS=$grp"
}
close $gate_ch

puts "DIAG_PLACED_DONE outdir=$outdir"
close_design
