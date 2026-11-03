set project_path [lindex $argv 0]
set migration_tcl [lindex $argv 1]
set frozen_dcp [lindex $argv 2]
if {$project_path eq "" || $migration_tcl eq "" || $frozen_dcp eq ""} {
    error "usage: migrate_xfft_manual_to_procise.tcl <project.xpr> <fmsh_migration_process.tcl> <frozen_ip.dcp>"
}

open_project $project_path
if {![file exists $frozen_dcp]} {
    error "frozen IP DCP does not exist: $frozen_dcp"
}

# Load the already patched, successfully synthesized IP before sourcing the
# migration helpers. The all-in-one function redundantly re-runs runEco0 and
# hangs on this tool combination.
open_checkpoint $frozen_dcp
set current_prj [get_property DIRECTORY [current_project]]
set top smartscan_fft_1024
set fmsh_root [file join $current_prj fmsh_file]
set procise_out [file join $fmsh_root procise_file]
file delete -force $fmsh_root
file mkdir $procise_out
write_edif -force [file join $fmsh_root ${top}.edif]
set fdc [open [file join $fmsh_root ${top}.xdc] w]
puts $fdc {create_clock -name aclk -period 10.000 [get_ports aclk]}
close $fdc
close_design

# Reuse the vendor EDIF/XDC translators and Procise project generator, while
# skipping only the failing duplicate ECO/synthesis stage.
source $migration_tcl -notrace
set procise_path [file join $::env(FMSH_PROCISE_PATH)]
translate_file_vvd_to_fmsh [file join $fmsh_root ${top}.edif] $procise_out $procise_path $current_prj
translate_file_vvd_to_fmsh [file join $fmsh_root ${top}.xdc] $procise_out $procise_path $current_prj
file rename -force [file join $procise_out ${top}.xdc] [file join $procise_out ${top}.fdc]
dsp_version_flag [file join $procise_out ${top}.edif] 13
create_procise_prj $current_prj $procise_path $top JFMQL30TAI676H none

foreach required [list \
    [file join $procise_out ${top}.edif] \
    [file join $procise_out ${top}.fdc] \
    [file join $procise_out $top ${top}.fpe]] {
    if {![file exists $required]} { error "migration output missing: $required" }
}
puts "XFFT_MIGRATION_RESULT result=PASS device=JFMQL30TAI676H mode=prepatched_ip_edif production_bitstream=NO"
close_project
exit 0
