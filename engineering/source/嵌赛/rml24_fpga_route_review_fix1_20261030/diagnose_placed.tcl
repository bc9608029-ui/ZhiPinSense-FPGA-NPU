# Read-only diagnostic session; never changes the active implementation run.
set OUT {F:/嵌赛/rml24_fpga_route_review_fix1_20261030/placed_diagnostics}
file mkdir $OUT
set_param general.maxThreads 1
open_checkpoint {F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/npu_base/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_combined_smartscan_placed.dcp}
proc emit {name command} {
    global OUT
    if {[catch {uplevel 1 $command} msg]} {
        set f [open [file join $OUT ${name}.error.txt] w]; puts $f $msg; close $f
        puts "DIAGNOSTIC_ERROR $name $msg"
    } else {puts "DIAGNOSTIC_OK $name"}
}
emit utilization {report_utilization -hierarchical -file [file join $OUT utilization_hier.rpt]}
emit timing {report_timing_summary -delay_type min_max -report_unconstrained -max_paths 10 -file [file join $OUT timing_placed.rpt]}
emit congestion {report_design_analysis -congestion -file [file join $OUT congestion.rpt]}
emit fanout {report_high_fanout_nets -timing -load_types -max_nets 30 -file [file join $OUT high_fanout.rpt]}
emit methodology {report_methodology -file [file join $OUT methodology.rpt]}
emit clocks {report_clock_interaction -file [file join $OUT clocks.rpt]}
emit exceptions {report_exceptions -file [file join $OUT exceptions.rpt]}
emit check {check_timing -verbose -file [file join $OUT check_timing.rpt]}
puts "PLACED_DIAGNOSTICS_COMPLETE"
close_design
exit
