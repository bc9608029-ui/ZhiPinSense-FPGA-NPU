# Controlled board-test candidate only. The two inherited NPU min-period
# endpoints remain visible. No timing/DRC check is disabled by this script.
set ROOT {E:/FPGA_Work/smartscan_prefetch_fix3_20261031}
set RUN [file join $ROOT fpga npu_base fpai_demo_vivado.runs impl_1]
set OUT [file join $ROOT outputs smartscan_fix2_candidate]
file mkdir $OUT
set TOP pl_ddr_mandatory_core_top_combined_smartscan
set RAW [file join $RUN ${TOP}.bit]
if {[file exists $RAW]} {error "RAW_BIT_ALREADY_EXISTS_REFUSE_OVERWRITE"}
set_param general.maxThreads 2
open_checkpoint [file join $ROOT reports_fix2 routed_fix2.dcp]
cd $RUN
source [file join $ROOT fpga npu_base ip_patch process_control write_bitstream_pre.tcl]
report_timing_summary -delay_type min_max -max_paths 10 -file [file join $OUT timing_after_vendor_pre.rpt]
set fh [open [file join $OUT timing_after_vendor_pre.rpt] r]
set report [read $fh];close $fh
set summary_found 0;set negative_min_pins {}
foreach line [split $report \n] {
    set fields [regexp -all -inline {\S+} $line]
    if {!$summary_found && [llength $fields] == 12} {
        set numeric 1
        foreach value $fields {if {![string is double -strict $value]} {set numeric 0}}
        if {$numeric} {
            foreach i {0 1 2 4 5 6} {if {[lindex $fields $i] < 0 || ($i in {2 6} && [lindex $fields $i] != 0)} {error "AFTER_PRE_SETUP_HOLD_FAILED"}}
            if {[lindex $fields 8] != -0.409 || [lindex $fields 9] != -0.479 || [lindex $fields 10] != 2} {error "AFTER_PRE_PULSE_SET_CHANGED"}
            set summary_found 1
        }
    }
    if {[llength $fields] >= 10 && [lrange $fields 0 1] eq {Min Period} && [string is double -strict [lindex $fields 7]] && [lindex $fields 7] < 0} {
        lappend negative_min_pins [lindex $fields end]
    }
}
set prefix {u_ps_ai_peripheral/ZGolo/u_AI_Mate_top/clkrst_wrapper_u0/AI_CORE_CLK/inst}
set expected [lsort [list $prefix/clkout1_buf/I $prefix/plle2_adv_inst/CLKOUT0]]
if {!$summary_found || [lsort $negative_min_pins] ne $expected} {error "AFTER_PRE_INHERITED_EXCEPTION_MISMATCH"}
puts "FIX2_PRE_BITGEN_INHERITED_EXCEPTION_GATE_PASS"
report_drc -file [file join $OUT drc_before_bitgen.rpt]
write_bitstream -force $RAW
if {![file exists $RAW] || [file size $RAW] < 1000000} {error "RAW_BIT_MISSING_OR_SHORT"}
file copy $RAW [file join $OUT smartscan_fix2_raw.bit]
puts "FIX2_RAW_BIT_WRITTEN size=[file size $RAW]"
source [file join $ROOT fpga npu_base ip_patch process_control write_bitstream_post.tcl]
set AUTO [file join $RUN ${TOP}_disable_icap.bit]
if {[file exists $AUTO]} {
    file copy $AUTO [file join $OUT smartscan_fix2_vendor_auto_disable_icap.bit]
    puts "FIX2_AUTO_DISABLE_ICAP_WRITTEN size=[file size $AUTO]"
}
puts "FIX2_VENDOR_BITGEN_FINISHED_WITH_INHERITED_NPU_EXCEPTION"
close_design
exit
