# Phase 2: generate the bitstream, then produce the disable_icap variant.
#
# Precondition: the routed timing/DRC gate (run_impl_route.tcl) has PASSED.
# This script launches impl_1 to write_bitstream (the FMSH write_bitstream
# pre/post hooks are already wired in the .xpr and fire automatically), then
# runs the vendor increment_bit_cfg_v3 flow to produce the disable_icap .bit
# that is actually programmed onto the FMQL30TAI (device JFMQL30TAI676H).

set project_dir {E:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga}
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set report_dir [file join $project_dir reports pl_ddr_mandatory_core_v1]
file mkdir $report_dir

open_project $project_file

launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 write_bitstream did not complete: STATUS=[get_property STATUS [get_runs impl_1]]"
}

set raw_bit [file join $project_dir fpai_demo_vivado.runs impl_1 pl_ddr_mandatory_core_top.bit]
if {![file exists $raw_bit]} {
    error "Raw bitstream not found after write_bitstream: $raw_bit"
}

# Vendor disable_icap conversion.  source run.tcl defines set_device and
# increment_bit_cfg_v3 (run.tcl's jfm_run also no-ops copy_patch because the
# project-local ip_patch already exists).
set ::env(JFM_PATH) $project_dir
source [file join $project_dir ip_patch run.tcl]
set_device JFMQL30TAI676H
set disable_bit [file join $project_dir fpai_demo_vivado.runs impl_1 pl_ddr_mandatory_core_top_disable_icap.bit]
increment_bit_cfg_v3 $raw_bit $disable_bit -disable_icap

if {![file exists $disable_bit]} {
    error "disable_icap bitstream not produced: $disable_bit"
}

set gate_ch [open [file join $report_dir bitstream_gate.txt] w]
puts $gate_ch "RAW_BIT=$raw_bit"
puts $gate_ch "RAW_BIT_SIZE=[file size $raw_bit]"
puts $gate_ch "DISABLE_ICAP_BIT=$disable_bit"
puts $gate_ch "DISABLE_ICAP_SIZE=[file size $disable_bit]"
close $gate_ch

puts "PL_DDR_IMPL_BITSTREAM_DONE RAW_SIZE=[file size $raw_bit] DISABLE_ICAP_SIZE=[file size $disable_bit]"
close_project
