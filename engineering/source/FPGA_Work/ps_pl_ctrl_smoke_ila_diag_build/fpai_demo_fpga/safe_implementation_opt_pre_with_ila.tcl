# Preserve the original project-local FMSH implementation pre-hook, then add
# the diagnostic ILA.  The installed Vivado/FMSH directories remain untouched.
set project_dir [file normalize [file dirname [info script]]]
set vendor_hook [file join $project_dir ip_patch process_control implementation_opt_pre.tcl]
if {![file exists $vendor_hook]} {
    error "Missing project-local FMSH implementation hook: $vendor_hook"
}
source $vendor_hook
source [file join $project_dir insert_gp0_ila.tcl]
