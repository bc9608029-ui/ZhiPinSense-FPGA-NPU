# analyze_cdc.tcl — open the EXISTING routed design and dump CDC + clock reports.
# Read-only: does not modify the project, does not rerun implementation.
# Usage: vivado -mode batch -source analyze_cdc.tcl
# Prints CDC_ANALYSIS_DONE on success.

set script_dir [file normalize [file dirname [info script]]]
set prj  [file join $script_dir vivado_prj hdmi_framebuffer_720p.xpr]
set rpt  [file join $script_dir reports]

if {![file exists $prj]} {
    error "project not found: $prj"
}
file mkdir $rpt

open_project $prj
open_run impl_1

report_clocks            -file [file join $rpt report_clocks.rpt]
report_clock_interaction -file [file join $rpt report_clock_interaction.rpt]
report_cdc -details      -file [file join $rpt report_cdc.rpt]

close_design
close_project
puts "CDC_ANALYSIS_DONE"
