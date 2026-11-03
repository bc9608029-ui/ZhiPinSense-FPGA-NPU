# Generate raw + disable_icap bitstream from the EXISTING routed DCP.
#
# Guard: refuse to re-run synth/impl.  We only ever run the write_bitstream step
# (and the vendor disable_icap conversion) on top of the already-routed,
# already-gated result.  If Vivado flags impl_1 NEEDS_REFRESH=true (any source
# change since route), we abort instead of silently re-running.
#
# The 1 GHz BUFG Min-Period pulse-width violation (Required 1.409 / Actual 1.000 /
# Slack -0.409) is NOT waived here: write_bitstream is gated on DRC only, not on
# timing, so it will emit the .bit while still reporting the known exception.

set project_dir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga}
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set report_dir [file join $project_dir reports pl_ddr_mandatory_core_v1]
file mkdir $report_dir

open_project $project_file

set st [get_property STATUS [get_runs impl_1]]
set nr [get_property NEEDS_REFRESH [get_runs impl_1]]
set pg [get_property PROGRESS [get_runs impl_1]]
puts "IMPL1_STATUS=$st"
puts "IMPL1_PROGRESS=$pg"
puts "IMPL1_NEEDS_REFRESH=$nr"

set routed_dcp [file join $project_dir fpai_demo_vivado.runs impl_1 pl_ddr_mandatory_core_top_routed.dcp]
if {![file exists $routed_dcp]} {
    error "Routed DCP missing, refusing to re-run: $routed_dcp"
}
if {[string equal -nocase $nr "true"]} {
    error "impl_1 NEEDS_REFRESH=true: a source changed since route. Refusing to re-run synth/impl."
}

# write_bitstream only (official FMSH pre/post hooks fire from the .xpr wiring).
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 write_bitstream did not complete: STATUS=[get_property STATUS [get_runs impl_1]]"
}

set raw_bit [file join $project_dir fpai_demo_vivado.runs impl_1 pl_ddr_mandatory_core_top.bit]
if {![file exists $raw_bit]} {
    error "Raw bitstream not found after write_bitstream: $raw_bit"
}
puts "RAW_BIT_OK size=[file size $raw_bit]"

# Vendor disable_icap conversion (official run.tcl flow).
set ::env(JFM_PATH) $project_dir
source [file join $project_dir ip_patch run.tcl]
set_device JFMQL30TAI676H
set disable_bit [file join $project_dir fpai_demo_vivado.runs impl_1 pl_ddr_mandatory_core_top_disable_icap.bit]
increment_bit_cfg_v3 $raw_bit $disable_bit -disable_icap

if {![file exists $disable_bit]} {
    error "disable_icap bitstream not produced: $disable_bit"
}
puts "DISABLE_ICAP_BIT_OK size=[file size $disable_bit]"

set gate_ch [open [file join $report_dir bitstream_gate.txt] w]
puts $gate_ch "RAW_BIT=$raw_bit"
puts $gate_ch "RAW_BIT_SIZE=[file size $raw_bit]"
puts $gate_ch "DISABLE_ICAP_BIT=$disable_bit"
puts $gate_ch "DISABLE_ICAP_SIZE=[file size $disable_bit]"
close $gate_ch

puts "PL_DDR_IMPL_BITSTREAM_DONE RAW_SIZE=[file size $raw_bit] DISABLE_ICAP_SIZE=[file size $disable_bit]"
close_project
