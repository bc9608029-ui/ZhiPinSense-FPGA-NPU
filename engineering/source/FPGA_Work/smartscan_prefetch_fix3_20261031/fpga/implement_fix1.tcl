# Independent project, reports first. No bitstream generation or board operations.
set ROOT {E:/FPGA_Work/smartscan_prefetch_fix3_20261031}
set OUT [file join $ROOT reports]
set_param general.maxThreads 2
open_project [file join $ROOT fpga npu_base fpai_demo_vivado.xpr]
if {[get_property PART [current_project]] ne "xc7z030ffg676-2"} {error "unexpected part"}
if {[get_property TOP [current_fileset]] ne "pl_ddr_mandatory_core_top_combined_smartscan"} {error "unexpected top"}
reset_run impl_1
launch_runs impl_1 -to_step route_design -jobs 1
wait_on_run impl_1
set st [get_property STATUS [get_runs impl_1]]
puts "FIX1_IMPL_STATUS=$st"
if {![string match {*route_design Complete*} $st]} {error "implementation did not complete routing"}
open_run impl_1
write_checkpoint -force [file join $OUT routed_fix1.dcp]
report_route_status -file [file join $OUT route_status.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -max_paths 20 -file [file join $OUT timing_summary.rpt]
report_timing -delay_type max -max_paths 20 -file [file join $OUT setup_paths.rpt]
report_timing -delay_type min -max_paths 20 -file [file join $OUT hold_paths.rpt]
report_drc -file [file join $OUT drc.rpt]
report_cdc -details -file [file join $OUT cdc.rpt]
report_clock_interaction -delay_type min_max -file [file join $OUT clock_interaction.rpt]
report_utilization -hierarchical -file [file join $OUT utilization.rpt]
check_timing -verbose -file [file join $OUT check_timing.rpt]
puts "FIX1_ROUTED_REPORTS_READY_NO_BITSTREAM"
close_project
exit 0
