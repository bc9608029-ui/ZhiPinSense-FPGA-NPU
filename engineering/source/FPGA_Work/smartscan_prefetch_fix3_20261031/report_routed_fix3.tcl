set ROOT {E:/FPGA_Work/smartscan_prefetch_fix3_20261031}
set OUT [file join $ROOT reports_fix3]
file mkdir $OUT
set_param general.maxThreads 2
open_checkpoint [file join $ROOT fpga npu_base fpai_demo_vivado.runs impl_1 pl_ddr_mandatory_core_top_combined_smartscan_routed.dcp]
write_checkpoint -force [file join $OUT routed_fix3.dcp]
report_route_status -file [file join $OUT route_status.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -max_paths 20 -file [file join $OUT timing_summary.rpt]
report_timing -delay_type max -max_paths 20 -file [file join $OUT setup_paths.rpt]
report_timing -delay_type min -max_paths 20 -file [file join $OUT hold_paths.rpt]
report_bus_skew -file [file join $OUT bus_skew.rpt]
report_drc -file [file join $OUT drc.rpt]
report_cdc -details -file [file join $OUT cdc.rpt]
report_clock_interaction -file [file join $OUT clock_interaction.rpt]
report_methodology -file [file join $OUT methodology.rpt]
report_utilization -hierarchical -file [file join $OUT utilization.rpt]
check_timing -verbose -file [file join $OUT check_timing.rpt]
puts "FIX2_ROUTED_REPORTS_READY_NO_BITSTREAM"
close_design
exit
