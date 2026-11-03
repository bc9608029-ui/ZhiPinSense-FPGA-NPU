set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_placed.dcp}
set out {F:/嵌赛/audit_pl_ddr_placed_reports}
file mkdir $out

open_checkpoint $dcp
report_timing -delay_type min -max_paths 30 -nworst 1 -path_type full_clock_expanded -file [file join $out worst_hold_30.rpt]
report_timing -delay_type max -max_paths 30 -nworst 1 -path_type full_clock_expanded -file [file join $out worst_setup_30.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $out timing_summary.rpt]
report_clock_interaction -file [file join $out clock_interaction.rpt]
report_cdc -details -file [file join $out cdc.rpt]
check_timing -verbose -file [file join $out check_timing.rpt]
catch {report_design_analysis -congestion -file [file join $out congestion.rpt]} congestion_result
set ch [open [file join $out audit_status.txt] w]
puts $ch "congestion_result=$congestion_result"
close $ch
close_design
exit
