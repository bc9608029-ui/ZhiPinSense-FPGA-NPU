set project_path [lindex $argv 0]
set migration_tcl [lindex $argv 1]
set ip_run [lindex $argv 2]
if {$project_path eq "" || $migration_tcl eq "" || $ip_run eq ""} {
    error "usage: migrate_xfft_to_procise.tcl <project.xpr> <fmsh_migration_process.tcl> <ip_synth_run>"
}
open_project $project_path
set ip_status [get_property STATUS [get_runs $ip_run]]
set ip_progress [get_property PROGRESS [get_runs $ip_run]]
if {![string match "*Complete*" $ip_status] || $ip_progress ne "100%"} {
    error "IP synthesis is not complete: run=$ip_run status=$ip_status progress=$ip_progress"
}
source $migration_tcl -notrace
# The vendor migration function assumes the active synthesis run is synth_1,
# even for its documented `-type ip -step synth` mode. Redirect only the
# `current_run -synthesis` query to the already-complete generated IP run.
rename current_run __vivado_current_run
proc current_run {args} {
    global ip_run
    if {[llength $args] == 1 && [lindex $args 0] eq "-synthesis"} {
        return [get_runs $ip_run]
    }
    return [uplevel 1 [linsert $args 0 __vivado_current_run]]
}
set migration_rc [catch {
    fmsh_migration_process -type ip -xdc on -prj on -mmi off -step synth \
        -procise_device JFMQL30TAI676H -dbg off
} migration_error migration_options]
if {$migration_rc} {
    puts stderr "XFFT_MIGRATION_TCL_ERROR message=$migration_error"
    if {[dict exists $migration_options -errorinfo]} {
        puts stderr [dict get $migration_options -errorinfo]
    }
    exit 3
}
puts "XFFT_MIGRATION_RESULT result=PASS device=JFMQL30TAI676H production_bitstream=NO"
close_project
exit 0
