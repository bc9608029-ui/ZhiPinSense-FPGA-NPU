# Report-only pass over the ALREADY-COMPLETED synth_1 run.
# The synthesis itself finished (synth_design Complete!); this script only
# regenerates the post-synth reports without re-running synthesis, and without
# the '-force' flag that Vivado 2018.3 does not accept on report_* commands.
set project_dir {E:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga}
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set report_dir [file join $project_dir reports pl_ddr_mandatory_core_v1]
file mkdir $report_dir

open_project $project_file
open_run synth_1

report_utilization -hierarchical -file [file join $report_dir post_synth_utilization_hier.rpt]
report_timing_summary -file [file join $report_dir post_synth_timing_summary.rpt]
report_clocks -file [file join $report_dir post_synth_clocks.rpt]
report_clock_interaction -file [file join $report_dir post_synth_clock_interaction.rpt]
report_cdc -details -file [file join $report_dir post_synth_cdc.rpt]
report_methodology -file [file join $report_dir post_synth_methodology.rpt]
check_timing -verbose -file [file join $report_dir post_synth_check_timing.rpt]
report_drc -file [file join $report_dir post_synth_drc.rpt]
if {[llength [get_bus_skews -quiet]] != 0} {
    report_bus_skew -file [file join $report_dir post_synth_bus_skew.rpt]
}
close_design

set summary_ch [open [file join $report_dir synthesis_gate.txt] w]
puts $summary_ch "TOP=pl_ddr_mandatory_core_top"
puts $summary_ch "PART=[get_property PART [current_project]]"
puts $summary_ch "SYNTH_STATUS=[get_property STATUS [get_runs synth_1]]"
close $summary_ch
close_project
puts "PL_DDR_MANDATORY_CORE_REPORTS_PASS"
