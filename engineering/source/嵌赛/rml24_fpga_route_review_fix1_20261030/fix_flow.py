from pathlib import Path
p=Path('F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/m4c_resume_route_smartscan.tcl')
s=p.read_text(encoding='utf-8')
a=s.index('# 关键交付物优先');b=s.index('# 时序口径',a)
s=s[:a]+'write_checkpoint -force [file join $OUTDIR routed_before_signoff.dcp]\n'+s[b:]
a=s.index('if {[catch {\n    set wns');b=s.index('# 报告',a)
s=s[:a]+'''set setup_paths [get_timing_paths -setup -max_paths 1]
set hold_paths [get_timing_paths -hold -max_paths 1]
if {[llength $setup_paths] != 1 || [llength $hold_paths] != 1} {error "timing path query missing"}
set wns [get_property SLACK $setup_paths]
set whs [get_property SLACK $hold_paths]
# Authoritative TNS/THS are in report_timing_summary.
'''+s[b:]
a=s.index('# 复制候选位流到输出目录')
s=s[:a]+'''report_route_status -file [file join $OUTDIR route_status.rpt]
check_timing -verbose -file [file join $OUTDIR check_timing.rpt]
if {![string is double -strict $wns] || ![string is double -strict $whs]} {error "invalid timing result"}
if {$wns < 0.0 || $whs < 0.0} {error "timing failed - checkpoint and reports preserved - no bitstream"}
# Review route completeness, unconstrained paths, CDC and DRC before enabling bitgen.
puts "==M4R_REPORT_REVIEW_REQUIRED_NO_BITSTREAM=="
close_project
exit 2
'''+s[a:]
# Bitgen/copy deliberately unreachable until independent signoff; no accidental promotion.
Path('m4c_reports_first_candidate.tcl').write_text(s,encoding='utf-8')
print('REPORTS_FIRST_WRITTEN_NOT_EXECUTED')
