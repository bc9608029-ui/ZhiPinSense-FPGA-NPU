# Route-only implementation pass for pl_ddr_mandatory_core_top.
#
# synth_1 and every OOC IP synth run are already complete and reused.  This
# script resets the (never-run) impl_1 and launches it to route_design ONLY --
# it deliberately stops BEFORE write_bitstream so the routed STA/DRC/CDC can be
# reviewed before any bitstream is produced (handoff step 7: locate every
# Error/Critical Warning before generating a bitstream).
#
# The FMSH opt_pre/opt_post and route_post hooks are already wired in the .xpr
# and fire automatically from the run directory; nothing here reconfigures them.

set project_dir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga}
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set report_dir [file join $project_dir reports pl_ddr_mandatory_core_v1]
file mkdir $report_dir

open_project $project_file

# Reset only the impl run; do not touch the completed synth_1 / OOC runs.
reset_run impl_1

launch_runs impl_1 -to_step route_design -jobs 1
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 route did not complete: STATUS=[get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
report_utilization      -hierarchical -file [file join $report_dir routed_utilization_hier.rpt]
report_timing_summary                 -file [file join $report_dir routed_timing_summary.rpt]
report_route_status                   -file [file join $report_dir routed_route_status.rpt]
report_drc                           -file [file join $report_dir routed_drc.rpt]
report_methodology                   -file [file join $report_dir routed_methodology.rpt]
report_cdc -details                  -file [file join $report_dir routed_cdc.rpt]
report_clock_interaction             -file [file join $report_dir routed_clock_interaction.rpt]
check_timing -verbose                -file [file join $report_dir routed_check_timing.rpt]

# Extract worst setup / hold slack (TNS/THS are read from routed_timing_summary.rpt).
set worst_setup [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
set worst_hold  [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
set wns [expr {[llength $worst_setup] ? [get_property SLACK $worst_setup] : 999.0}]
set whs [expr {[llength $worst_hold]  ? [get_property SLACK $worst_hold]  : 999.0}]

set gate_ch [open [file join $report_dir routed_timing_gate.txt] w]
puts $gate_ch "IMPL_STATUS=[get_property STATUS [get_runs impl_1]]"
puts $gate_ch "WNS=$wns"
puts $gate_ch "WHS=$whs"
puts $gate_ch "SETUP_PATH=[expr {[llength $worst_setup] ? [get_property STARTPOINT_PIN $worst_setup] : ""}] -> [expr {[llength $worst_setup] ? [get_property ENDPOINT_PIN $worst_setup] : ""}]"
puts $gate_ch "HOLD_PATH=[expr {[llength $worst_hold] ? [get_property STARTPOINT_PIN $worst_hold] : ""}] -> [expr {[llength $worst_hold] ? [get_property ENDPOINT_PIN $worst_hold] : ""}]"
close $gate_ch
close_design

set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]
puts "PL_DDR_IMPL_ROUTE_DONE WNS=$wns WHS=$whs TIMING_OK=$timing_ok"
close_project
