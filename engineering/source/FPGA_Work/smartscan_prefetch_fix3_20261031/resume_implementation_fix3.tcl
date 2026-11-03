set ROOT {E:/FPGA_Work/smartscan_prefetch_fix3_20261031}
set OUT [file join $ROOT reports_fix3]
file mkdir $OUT
set_param general.maxThreads 2
open_project [file join $ROOT fpga npu_base fpai_demo_vivado.xpr]
if {[get_property PART [current_project]] ne "xc7z030ffg676-2"} {error "PART_MISMATCH"}
if {[get_property TOP [current_fileset]] ne "pl_ddr_mandatory_core_top_combined_smartscan"} {error "TOP_MISMATCH"}
set st [get_property STATUS [get_runs impl_1]]
puts "RESUME_OPT_STATUS=$st"
set opt [file join $ROOT fpga npu_base fpai_demo_vivado.runs impl_1 pl_ddr_mandatory_core_top_combined_smartscan_opt.dcp]
if {$st ne "Not started place_design" || ![file exists $opt]} {error "OPT_RESUME_NOT_VERIFIED"}
open_run impl_1
report_utilization -hierarchical -file [file join $OUT utilization_opted.rpt]
set fft_n 0
array set n {buffer 0 engine_in 0 engine_out 0 scan_in 0 fft_ram 0 prefetch 0}
foreach c [get_cells -hier -filter {IS_PRIMITIVE == 1}] {
    set name [get_property NAME $c]
    set ref [get_property REF_NAME $c]
    if {[string match {u_smart_scan/u_scan/u_fft/*} $name]} {incr fft_n}
    if {![string match {RAMB*} $ref]} {continue}
    foreach {key pattern} {
        buffer {u_smart_scan/u_scan/u_buffers/*}
        engine_in {u_engine/input_adapter/cdc_fifo/*}
        engine_out {u_engine/output_adapter/cdc_fifo/*}
        scan_in {u_smart_scan/input_adapter/cdc_fifo/*}
        fft_ram {u_smart_scan/u_scan/u_fft/*}
        prefetch {u_smart_scan/u_scan/u_fft/u_prefetch/*}
    } {if {[string match $pattern $name]} {incr n($key)}}
}
set f [open [file join $OUT functionality_resource_gate.txt] w]
puts $f "FFT_PRIMITIVES=$fft_n"
foreach key [array names n] {puts $f "$key=$n($key)"}
close $f
if {$fft_n < 500} {error "FFT_DATAPATH_PRUNED cells=$fft_n"}
foreach key {buffer engine_in engine_out scan_in fft_ram prefetch} {
    if {$n($key) < 1} {error "MISSING_RAM_IN_DATAPATH $key"}
}
puts "FIX2_FUNCTION_RESOURCE_GATE_PASS"
close_design
launch_runs impl_1 -to_step route_design -jobs 1
wait_on_run impl_1
set rst [get_property STATUS [get_runs impl_1]]
puts "FINAL_ROUTE_STATUS=$rst"
set routed [file join $ROOT fpga npu_base fpai_demo_vivado.runs impl_1 pl_ddr_mandatory_core_top_combined_smartscan_routed.dcp]
if {![file exists $routed] || !([string match {*route_design Complete*} $rst] || $rst eq "Not started write_bitstream")} {error "ROUTE_FAILED"}
open_run impl_1
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
close_project
exit
