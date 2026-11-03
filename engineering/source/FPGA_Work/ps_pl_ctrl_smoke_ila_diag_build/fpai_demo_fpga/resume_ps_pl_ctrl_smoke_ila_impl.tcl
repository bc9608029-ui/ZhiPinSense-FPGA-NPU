set project_dir [file normalize [file dirname [info script]]]
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set report_dir [file join $project_dir reports ps_pl_ctrl_smoke_ila_diag]
file mkdir $report_dir

open_project $project_file
set_property STEPS.OPT_DESIGN.TCL.PRE \
    [file join $project_dir safe_implementation_opt_pre_with_ila.tcl] [get_runs impl_1]
set_property STEPS.OPT_DESIGN.TCL.POST \
    [file join $project_dir safe_implementation_opt_post_with_debug_hub.tcl] [get_runs impl_1]

if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "Existing synthesis is not complete"
}
open_run synth_1
set dbg_nets {}
for {set i 0} {$i < 141} {incr i} {
    set bit_name [format {dbg_gp0_read[%d]} $i]
    set bit_net [get_nets -quiet $bit_name]
    if {[llength $bit_net] != 1} {
        error "Expected exactly one top-level net named $bit_name, found [llength $bit_net]"
    }
    lappend dbg_nets [lindex $bit_net 0]
}
puts "GP0_DEBUG_BITS_AFTER_SYNTH=[llength $dbg_nets]"
if {[llength $dbg_nets] != 141} {
    error "Expected 141 dbg_gp0_read bits, found [llength $dbg_nets]"
}
close_design

reset_run impl_1
launch_runs impl_1 -to_step route_design -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 route failed: [get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
report_utilization -file [file join $report_dir routed_utilization.rpt]
report_timing_summary -file [file join $report_dir routed_timing_summary.rpt]
report_route_status -file [file join $report_dir routed_route_status.rpt]
report_drc -file [file join $report_dir routed_drc.rpt]
report_methodology -file [file join $report_dir routed_methodology.rpt]
report_debug_core -file [file join $report_dir routed_debug_cores.rpt]
set setup_path [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
set hold_path [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
if {$wns < 0.0 || $whs < 0.0} {
    error "Timing gate failed: WNS=$wns WHS=$whs"
}
close_design

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "bitstream failed: [get_property STATUS [get_runs impl_1]]"
}
open_run impl_1
write_debug_probes -force [file join $report_dir ps_pl_ctrl_smoke_ila_diag.ltx]
close_design

set summary_ch [open [file join $report_dir build_summary.txt] w]
puts $summary_ch "TOP=ps_pl_ctrl_smoke_top"
puts $summary_ch "PART=[get_property PART [current_project]]"
puts $summary_ch "WNS=$wns"
puts $summary_ch "WHS=$whs"
puts $summary_ch "ILA_PROBE_BITS=141"
puts $summary_ch "ILA_DEPTH=1024"
close $summary_ch
close_project
puts "PS_PL_CTRL_SMOKE_ILA_DIAG_BUILD_PASS"
