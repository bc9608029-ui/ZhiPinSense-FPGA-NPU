# build_xfft_z030.tcl — re-synthesize the frozen XFFT 9.1 IP targeting the board
# part xc7z030ffg676-2 (standard Unisim primitives) and emit a Vivado-linkable DCP.
#
# WHY: the migrated Procise EDIF (smartscan_fft_1024.edif) carries FMSH primitive
# names (CU48E1/DRURE/LCARRY4/RAMH18E1/SHR16E/SHRC32E). Vivado cannot resolve them
# (probe_read_edif.tcl showed 4398 DRURE + 13 CU48E1 + 8 RAMH18E1 + ... unresolved
# black boxes), so that netlist is Procise-only. The board m3/m4 flow P&Rs in Vivado
# against xc7z030ffg676-2 (its own AI_Mate.edif uses standard DSP48E1/RAMB18E1/FDRE),
# therefore the FFT core must be a Vivado-synthesized DCP for that part.
#
# This is a byte-consistent retarget of build_xfft_1024.tcl (same frozen CONFIG dict,
# same FMSH ip_patch load) with only the -part changed and the Procise migration
# dropped. Output: smartscan_fft_1024_z030_synth.dcp (standard primitives).

set run_dir [file normalize [file dirname [info script]]]
set out_dir [file join $run_dir xfft_z030]
file mkdir $out_dir
set work_dir [file join $out_dir work_build]
create_project -force smartscan_fft_z030 $work_dir -part xc7z030ffg676-2

# FMSH patch must be loaded before IP generation (identical to build_xfft_1024.tcl).
source D:/FMSH/JFM_Kits/ip_patch/run.tcl
show_ip_patch_version
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

reset_target all $ip
generate_target all $ip
create_ip_run $ip
launch_runs smartscan_fft_1024_synth_1 -jobs 1
wait_on_run smartscan_fft_1024_synth_1
set status [get_property STATUS [get_runs smartscan_fft_1024_synth_1]]
set progress [get_property PROGRESS [get_runs smartscan_fft_1024_synth_1]]
puts "XFFT_Z030_SYNTH_STATUS status=$status progress=$progress"
if {![string match "*Complete*" $status] || $progress ne "100%"} {
    puts "XFFT_Z030_BUILD_RESULT result=FAIL"
    close_project
    exit 2
}
open_run smartscan_fft_1024_synth_1
report_utilization -file [file join $out_dir xfft_z030_utilization.rpt]
report_timing_summary -file [file join $out_dir xfft_z030_timing_summary.rpt]
write_checkpoint -force [file join $out_dir smartscan_fft_1024_z030_synth.dcp]
puts "XFFT_Z030_BUILD_RESULT result=PASS part=xc7z030ffg676-2 ip=xilinx.com:ip:xfft:9.1 primitives=standard_unisim production_bitstream=NO"
close_project
exit 0
