# Safe wrapper around the unmodified FMSH synthesis pre-hook.
#
# The vendor hook unconditionally copies the selected device's zynq.lib and
# zynq.padr into the Vivado installation on every synthesis run.  For this
# machine those installed files are already byte-identical to the project-local
# FMSH 030AI files.  Intercept only those redundant, identical copies so the
# normal vendor hook can run without writing D:/Xilinx2018.3.

set project_dir [file normalize [file dirname [info script]]]
set vendor_hook [file join $project_dir ip_patch process_control synthesis_pre.tcl]

proc fmsh_files_are_identical {source_path destination_path} {
    if {![::fmsh_builtin_file exists $source_path] ||
        ![::fmsh_builtin_file exists $destination_path]} {
        return 0
    }
    if {[::fmsh_builtin_file size $source_path] !=
        [::fmsh_builtin_file size $destination_path]} {
        return 0
    }

    set source_channel [open $source_path rb]
    set destination_channel [open $destination_path rb]
    fconfigure $source_channel -translation binary -encoding binary
    fconfigure $destination_channel -translation binary -encoding binary
    set identical 1
    while {![eof $source_channel] && ![eof $destination_channel]} {
        set source_chunk [read $source_channel 1048576]
        set destination_chunk [read $destination_channel 1048576]
        if {$source_chunk ne $destination_chunk} {
            set identical 0
            break
        }
    }
    close $source_channel
    close $destination_channel
    return $identical
}

rename file ::fmsh_builtin_file
proc file {subcommand args} {
    if {$subcommand eq "copy" && [llength $args] >= 2} {
        set source_path [lindex $args end-1]
        set destination_path [lindex $args end]
        set destination_normalized [::fmsh_builtin_file normalize $destination_path]
        set protected_dir [::fmsh_builtin_file normalize \
            {D:/Xilinx2018.3/Vivado/2018.3/data/parts/xilinx/zynq/devint}]
        set protected_lib [::fmsh_builtin_file join $protected_dir zynq.lib]
        set protected_padr [::fmsh_builtin_file join $protected_dir zynq.padr]

        if {([string equal -nocase $destination_normalized $protected_lib] ||
             [string equal -nocase $destination_normalized $protected_padr]) &&
            [fmsh_files_are_identical $source_path $destination_path]} {
            puts "FMSH_SAFE_HOOK: skipped byte-identical installation copy: $destination_normalized"
            return $destination_path
        }
    }

    set command [linsert $args 0 ::fmsh_builtin_file $subcommand]
    return [uplevel 1 $command]
}

set hook_status [catch {source $vendor_hook} hook_result hook_options]
rename file {}
rename ::fmsh_builtin_file file
rename fmsh_files_are_identical {}

if {$hook_status} {
    return -options $hook_options $hook_result
}

