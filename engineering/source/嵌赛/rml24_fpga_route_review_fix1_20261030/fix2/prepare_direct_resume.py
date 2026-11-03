from pathlib import Path
HERE=Path(__file__).resolve().parent
text=(HERE/'resume_guarded.tcl').read_text(encoding='utf-8')
text=text.replace('open_run impl_1','open_checkpoint [file join $RUN ${TOP}_opt.dcp]',1)
start=text.index('close_design\nlaunch_runs impl_1 -to_step route_design')
end=text.index('write_checkpoint -force [file join $OUT routed_fix2.dcp]',start)
middle='''# Direct checkpoint implementation avoids partial-run open_run limitations.
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
'''
text=text[:start]+middle+text[end:]
(HERE/'direct_resume_guarded.tcl').write_text(text,encoding='utf-8')
print('DIRECT_RESUME_PREPARED')
