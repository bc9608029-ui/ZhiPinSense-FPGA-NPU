# Full implementation re-run with the CDC async clock-group isolation applied.
#
# Adds cdc_async_groups.xdc to the active constrs_1 fileset, resets the
# (aborted) impl_1, and re-runs opt_design -> place_design -> route_design.
# Stops BEFORE write_bitstream: the routed STA/DRC/CDC/check_timing must be
# reviewed first.  -jobs 1 to avoid the memory peaks that caused the earlier
# OOM.  synth_1 and every OOC IP run are reused (already complete).

set project_dir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga}
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set cdc_xdc {F:/FPGA_Work/pl_ddr_mandatory_core_v1/pl_ddr_integration_v1/cdc_async_groups.xdc}
set report_dir [file join $project_dir reports pl_ddr_mandatory_core_v1]
file mkdir $report_dir

open_project $project_file

# Add the CDC isolation constraint to the active constraint set.
add_files -fileset constrs_1 -norecurse $cdc_xdc
puts "CDC_XDC_ADDED=[file tail $cdc_xdc]"

# Reset only the impl run; reuse completed synth_1 / OOC runs.
reset_run impl_1

launch_runs impl_1 -to_step route_design -jobs 1
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 route did not complete: STATUS=[get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
report_utilization      -hierarchical -file [file join $report_dir cdc_routed_utilization_hier.rpt]
report_timing_summary                 -file [file join $report_dir cdc_routed_timing_summary.rpt]
report_route_status                   -file [file join $report_dir cdc_routed_route_status.rpt]
report_drc                           -file [file join $report_dir cdc_routed_drc.rpt]
report_methodology                   -file [file join $report_dir cdc_routed_methodology.rpt]
report_cdc -details                  -file [file join $report_dir cdc_routed_cdc.rpt]
report_clock_interaction             -file [file join $report_dir cdc_routed_clock_interaction.rpt]
check_timing -verbose                -file [file join $report_dir cdc_routed_check_timing.rpt]

# Extract worst setup / hold slack (TNS/THS are read from cdc_routed_timing_summary.rpt).
set worst_setup [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
set worst_hold  [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
set wns [expr {[llength $worst_setup] ? [get_property SLACK $worst_setup] : 999.0}]
set whs [expr {[llength $worst_hold]  ? [get_property SLACK $worst_hold]  : 999.0}]

set gate_ch [open [file join $report_dir cdc_routed_timing_gate.txt] w]
puts $gate_ch "IMPL_STATUS=[get_property STATUS [get_runs impl_1]]"
puts $gate_ch "WNS=$wns"
puts $gate_ch "WHS=$whs"
puts $gate_ch "SETUP_PATH=[expr {[llength $worst_setup] ? [get_property STARTPOINT_PIN $worst_setup] : ""}] -> [expr {[llength $worst_setup] ? [get_property ENDPOINT_PIN $worst_setup] : ""}]"
puts $gate_ch "HOLD_PATH=[expr {[llength $worst_hold] ? [get_property STARTPOINT_PIN $worst_hold] : ""}] -> [expr {[llength $worst_hold] ? [get_property ENDPOINT_PIN $worst_hold] : ""}]"
close $gate_ch
close_design

puts "PL_DDR_IMPL_CDC_ROUTE_DONE WNS=$wns WHS=$whs"
close_project
