set run_dir [file normalize [file dirname [info script]]]
set work_dir [file join $run_dir work_build]
file mkdir $work_dir
create_project -force smartscan_fft_build $work_dir -part xc7k325tffg900-2

# FMSH patch must be loaded before IP generation. The installed patch reports
# version 5.3.1.8 and explicitly replaces XFFT/FIR/DDS lower-level libraries.
source D:/FMSH/JFM_Kits/ip_patch/run.tcl
show_ip_patch_version
# add_hook_tcl_to_prj overwrites a set of files inside the Vivado installation.
# That tree is read-only to a normal user. Permit a skipped overwrite only when
# source and installed destination are byte-identical; fail closed on the first
# difference. Every project-local hook still runs normally.
rename file __fmsh_orig_file
proc file {subcmd args} {
    if {$subcmd eq "copy" && [llength $args] >= 2} {
        set src [lindex $args end-1]
        set dst [lindex $args end]
        set dst_norm [string map {\\ /} $dst]
        if {[string match "D:/Xilinx2018.3/*" $dst_norm] &&
            [__fmsh_orig_file exists $src] && [__fmsh_orig_file exists $dst]} {
            set fs [open $src rb]
            fconfigure $fs -translation binary
            set source_bytes [read $fs]
            close $fs
            set fd [open $dst rb]
            fconfigure $fd -translation binary
            set dest_bytes [read $fd]
            close $fd
            if {$source_bytes eq $dest_bytes} {
                puts "FMSH_INSTALL_COPY_SKIPPED reason=installed_file_byte_identical dst=$dst_norm"
                return ""
            }
            error "FMSH_INSTALL_COPY_REQUIRED_DIFFERENT_FILE dst=$dst_norm"
        }
    }
    return [uplevel 1 [linsert $args 0 __fmsh_orig_file $subcmd]]
}
add_hook_tcl_to_prj
rename file {}
rename __fmsh_orig_file file

create_ip -name xfft -vendor xilinx.com -library ip -version 9.1 \
          -module_name smartscan_fft_1024
set ip [get_ips smartscan_fft_1024]
set_property -dict [list \
    CONFIG.transform_length {1024} \
    CONFIG.implementation_options {pipelined_streaming_io} \
    CONFIG.data_format {fixed_point} \
    CONFIG.input_width {16} \
    CONFIG.phase_factor_width {16} \
    CONFIG.scaling_options {unscaled} \
    CONFIG.output_ordering {natural_order} \
    CONFIG.xk_index {true} \
    CONFIG.aresetn {true} \
    CONFIG.throttle_scheme {realtime} \
    CONFIG.target_clock_frequency {100} \
    CONFIG.target_data_throughput {100} \
] $ip

set f [open [file join $run_dir xfft_frozen_properties.txt] w]
foreach p [lsort [list_property $ip]] {
    if {[string match "CONFIG.*" $p]} {
        puts $f "$p=[get_property $p $ip]"
    }
}
close $f

reset_target all $ip
generate_target all $ip
create_ip_run $ip
launch_runs smartscan_fft_1024_synth_1 -jobs 4
wait_on_run smartscan_fft_1024_synth_1
set status [get_property STATUS [get_runs smartscan_fft_1024_synth_1]]
set progress [get_property PROGRESS [get_runs smartscan_fft_1024_synth_1]]
puts "XFFT_SYNTH_STATUS status=$status progress=$progress"
if {![string match "*Complete*" $status] || $progress ne "100%"} {
    puts "XFFT_BUILD_RESULT result=FAIL"
    exit 2
}
open_run smartscan_fft_1024_synth_1
report_utilization -file [file join $run_dir xfft_vivado_utilization.rpt]
report_timing_summary -file [file join $run_dir xfft_vivado_timing_summary.rpt]
write_checkpoint -force [file join $run_dir smartscan_fft_1024_synth.dcp]
set fmsh_root [file join $work_dir fmsh_file]
set procise_out [file join $fmsh_root procise_file]
file delete -force $fmsh_root
file mkdir $procise_out
write_edif -force [file join $fmsh_root smartscan_fft_1024.edif]
set fdc [open [file join $fmsh_root smartscan_fft_1024.xdc] w]
puts $fdc {create_clock -name aclk -period 10.000 [get_ports aclk]}
close $fdc
close_design

# Export from the still-open successful synthesis session. Reopening the XFFT
# checkpoint in this installation emits unbounded `Unrecognized character`;
# the vendor translators themselves work on the emitted EDIF/XDC.
set migration_tcl D:/FMSH/JFM_Kits/ip_patch/fmsh_migration_process/fmsh_migration_process.tcl
source $migration_tcl -notrace
set procise_path [file join $::env(FMSH_PROCISE_PATH)]
translate_file_vvd_to_fmsh [file join $fmsh_root smartscan_fft_1024.edif] $procise_out $procise_path $work_dir
translate_file_vvd_to_fmsh [file join $fmsh_root smartscan_fft_1024.xdc] $procise_out $procise_path $work_dir
file rename -force [file join $procise_out smartscan_fft_1024.xdc] [file join $procise_out smartscan_fft_1024.fdc]
dsp_version_flag [file join $procise_out smartscan_fft_1024.edif] 13
create_procise_prj $work_dir $procise_path smartscan_fft_1024 JFMQL30TAI676H none
if {![file exists [file join $procise_out smartscan_fft_1024 smartscan_fft_1024.fpe]]} {
    error "Procise XFFT project was not created"
}
puts "XFFT_PROCISE_EXPORT result=PASS mode=same_synthesis_session production_bitstream=NO"
puts "XFFT_BUILD_RESULT result=PASS ip=xilinx.com:ip:xfft:9.1 patched=YES production_bitstream=NO"
exit 0
