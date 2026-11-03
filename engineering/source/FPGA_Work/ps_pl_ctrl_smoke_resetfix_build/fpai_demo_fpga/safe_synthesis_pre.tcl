# Run the unmodified FMSH synthesis pre-hook without rewriting an identical
# device database in the Vivado installation.  If a requested destination is
# absent or differs from the project-local source, the normal copy is retained
# and the build will fail under the read-only installation policy rather than
# silently using an unverified database.
rename file __fmsh_orig_file

proc __fmsh_files_identical {source destination} {
    if {![__fmsh_orig_file isfile $source] || ![__fmsh_orig_file isfile $destination]} {
        return 0
    }
    if {[__fmsh_orig_file size $source] != [__fmsh_orig_file size $destination]} {
        return 0
    }

    set source_channel [open $source rb]
    set destination_channel [open $destination rb]
    fconfigure $source_channel -translation binary -encoding binary
    fconfigure $destination_channel -translation binary -encoding binary
    set source_data [read $source_channel]
    set destination_data [read $destination_channel]
    close $source_channel
    close $destination_channel
    return [string equal $source_data $destination_data]
}

proc file {subcommand args} {
    if {$subcommand eq "copy" && [llength $args] >= 2} {
        set source [lindex $args end-1]
        set destination [lindex $args end]
        set destination_normalized [string tolower [__fmsh_orig_file normalize $destination]]
        set vivado_database_root [string tolower [__fmsh_orig_file normalize {D:/Xilinx2018.3/Vivado/2018.3/data/parts/xilinx/zynq/devint}]]
        if {[string first $vivado_database_root $destination_normalized] == 0 &&
            [__fmsh_files_identical $source $destination]} {
            puts "FMSH_SAFE_PREHOOK: identical installed device file retained: $destination"
            return $destination
        }
    }
    return [uplevel 1 [linsert $args 0 __fmsh_orig_file $subcommand]]
}

set original_pre_hook [__fmsh_orig_file join [__fmsh_orig_file dirname [info script]] ip_patch process_control synthesis_pre.tcl]
set source_status [catch {source $original_pre_hook} source_result source_options]

rename file {}
rename __fmsh_orig_file file
rename __fmsh_files_identical {}

if {$source_status} {
    return -options $source_options $source_result
}
