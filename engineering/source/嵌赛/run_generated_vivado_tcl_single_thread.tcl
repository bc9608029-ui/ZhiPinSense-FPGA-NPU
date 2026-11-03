if {[llength $argv] == 1} {
    set generated_script_arg [lindex $argv 0]
} elseif {[info exists ::env(CODEX_GENERATED_VIVADO_TCL)]} {
    set generated_script_arg $::env(CODEX_GENERATED_VIVADO_TCL)
} else {
    error "Set CODEX_GENERATED_VIVADO_TCL to the generated run Tcl path"
}

set generated_script [file normalize $generated_script_arg]
set run_dir [file dirname $generated_script]

cd $run_dir
puts "RUNNING_GENERATED_SCRIPT_SINGLE_THREAD=$generated_script"

# Preserve the generated script byte-for-byte (important for non-ASCII paths)
# and intercept only its maxThreads setting while it is sourced.
rename set_param codex_original_set_param
proc set_param {name value} {
    if {$name eq "general.maxThreads"} {
        set value 1
    }
    uplevel 1 [list codex_original_set_param $name $value]
}
source $generated_script
