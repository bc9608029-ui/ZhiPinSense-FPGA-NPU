set ROOT {F:/FPGA_Work/smartscan_bram_fix1_20261030}
set OUT [file join $ROOT reports_fix2]
file mkdir $OUT
set_param general.maxThreads 2
open_project [file join $ROOT fpga npu_base fpai_demo_vivado.xpr]
if {[get_property PART [current_project]] ne "xc7z030ffg676-2"} {error "PART_MISMATCH"}
if {[get_property TOP [current_fileset]] ne "pl_ddr_mandatory_core_top_combined_smartscan"} {error "TOP_MISMATCH"}
# FMSH/Vivado 2018.3 reports a successful partial run as
# "Not started place_design" (50%), not "opt_design Complete".
# Validate concrete completion stamps and the fresh checkpoint instead.
set RUN [get_property DIRECTORY [get_runs impl_1]]
set TOP [get_property TOP [current_fileset]]
proc require_step {step checkpoint} {
    global RUN
    set begin [file join $RUN .${step}.begin.rst]
    set end [file join $RUN .${step}.end.rst]
    set err [file join $RUN .${step}.error.rst]
    set dcp [file join $RUN $checkpoint]
    foreach p [list $begin $end $dcp] {if {![file exists $p]} {error "MISSING_STEP_ARTIFACT $p"}}
    if {[file exists $err]} {error "STEP_ERROR_STAMP $step"}
    if {[file mtime $end] < [file mtime $begin] || [file mtime $dcp] < [file mtime $begin]} {error "STALE_STEP_ARTIFACT $step"}
    puts "FIX2_STEP_ARTIFACTS_OK $step status=[get_property STATUS [get_runs impl_1]]"
}
require_step opt_design ${TOP}_opt.dcp
open_checkpoint [file join $RUN ${TOP}_opt.dcp]
report_utilization -hierarchical -file [file join $OUT utilization_opted.rpt]
set fft_n 0
array set n {buffer 0 engine_in 0 engine_out 0 scan_in 0 fft_ram 0}
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
    } {if {[string match $pattern $name]} {incr n($key)}}
}
set f [open [file join $OUT functionality_resource_gate.txt] w]
puts $f "FFT_PRIMITIVES=$fft_n"
foreach key [array names n] {puts $f "$key=$n($key)"}
close $f
if {$fft_n < 500} {error "FFT_DATAPATH_PRUNED cells=$fft_n"}
foreach key {buffer engine_in engine_out scan_in fft_ram} {
    if {$n($key) < 1} {error "MISSING_RAM_IN_DATAPATH $key"}
}
puts "FIX2_FUNCTION_RESOURCE_GATE_PASS"
# Direct checkpoint implementation avoids partial-run open_run limitations.
# This is the same checkpoint flow already used by the earlier B-line resume.
puts "FIX2_PLACE_START"
place_design
write_checkpoint -force [file join $OUT placed_fix2.dcp]
report_utilization -file [file join $OUT utilization_placed.rpt]
report_control_sets -verbose -file [file join $OUT control_sets_placed.rpt]
report_design_analysis -congestion -file [file join $OUT congestion_placed.rpt]
report_timing_summary -delay_type min_max -max_paths 10 -file [file join $OUT timing_placed.rpt]
puts "FIX2_ROUTE_START"
if {[catch {route_design} route_error]} {
    write_checkpoint -force [file join $OUT route_failed_fix2.dcp]
    error "FIX2_ROUTE_FAILED $route_error"
}
write_checkpoint -force [file join $OUT routed_before_vendor_post.dcp]
report_timing_summary -delay_type min_max -report_unconstrained -max_paths 20 -file [file join $OUT timing_before_vendor_post.rpt]
report_exceptions -file [file join $OUT exceptions_before_vendor_post.rpt]
# Preserve the project flow's original vendor post-route processing, unchanged.
# Its relative paths assume the implementation run directory.
cd $RUN
source [file join $ROOT fpga npu_base ip_patch process_control implementation_route_post.tcl]
report_exceptions -file [file join $OUT exceptions_after_vendor_post.rpt]
write_checkpoint -force [file join $OUT routed_fix2.dcp]
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
