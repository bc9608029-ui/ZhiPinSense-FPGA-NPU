from pathlib import Path
HERE=Path(__file__).resolve().parent
text=(HERE/'implement_guarded.tcl').read_text(encoding='utf-8')
old='''reset_run impl_1
launch_runs impl_1 -to_step opt_design -jobs 1
wait_on_run impl_1
if {![string match {*opt_design Complete*} [get_property STATUS [get_runs impl_1]]]} {error "OPT_FAILED"}
'''
assert old in text
new='''# FMSH/Vivado 2018.3 reports a successful partial run as
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
'''
text=text.replace(old,new)
old='if {![string match {*route_design Complete*} [get_property STATUS [get_runs impl_1]]]} {error "ROUTE_FAILED"}'
assert old in text
text=text.replace(old,'require_step route_design ${TOP}_routed.dcp')
(HERE/'resume_guarded.tcl').write_text(text,encoding='utf-8')
print('RESUME_SCRIPT_READY_NO_SYNTH_RESET')
