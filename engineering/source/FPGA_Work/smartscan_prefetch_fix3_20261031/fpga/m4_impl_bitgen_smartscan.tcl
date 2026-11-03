# m4_impl_bitgen_smartscan.tcl — smart-scan combined top impl + bitgen (step 2 of 3).
#
# Precondition: m3_synth_smartscan.tcl succeeded (synth_1 checkpoint exists).
# Reuses that checkpoint for impl_1 -> write_bitstream, then emits timing / DRC /
# clock / CDC / utilization / power reports from the routed DCP and copies the raw
# .bit to the candidate output dir.  Mirrors m4_impl_bitgen_combined.tcl.

set PRJ     {E:/FPGA_Work/smartscan_prefetch_fix3_20261031/fpga/npu_base/fpai_demo_vivado.xpr}
set OUTDIR  {E:/FPGA_Work/smartscan_prefetch_fix3_20261031/outputs/smartscan_candidate_v1/reports}
set BITDIR  {E:/FPGA_Work/smartscan_prefetch_fix3_20261031/outputs/smartscan_candidate_v1/bitstream}
set CDC_XDC {E:/FPGA_Work/smartscan_prefetch_fix3_20261031/fpga/pl_ddr_integration_v1/cdc_async_groups.xdc}

file mkdir $OUTDIR
file mkdir $BITDIR

open_project $PRJ
puts "==M4S_OPEN_OK top=[get_property top [current_fileset]]=="

if {![file exists $CDC_XDC]} {
  puts "==M4S_CDC_XDC_MISSING== $CDC_XDC"
  close_project
  exit 1
}
set cdc_active 0
foreach f [get_files -of_objects [get_filesets constrs_1]] {
  if {[string equal $f $CDC_XDC]} { set cdc_active 1 }
}
if {!$cdc_active} {
  puts "==M4S_CDC_XDC_NOT_ACTIVE== $CDC_XDC"
  close_project
  exit 1
}
puts "==M4S_CDC_XDC_ACTIVE=[file tail $CDC_XDC]=="

reset_run impl_1
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1

set st [get_property STATUS [get_runs impl_1]]
set pr [get_property PROGRESS [get_runs impl_1]]
puts "==M4S_IMPL_STATUS=${st}=="
puts "==M4S_IMPL_PROGRESS=${pr}=="

if {$pr ne "100%"} {
  puts "==M4S_IMPL_FAILED== status=${st} see fpga/npu_base/fpai_demo_vivado.runs/impl_1/runme.log"
  close_project
  exit 1
}

open_run impl_1
set top [get_property top [current_fileset]]
report_timing_summary  -delay_type min_max -max_paths 10 -file [file join $OUTDIR timing_summary_routed.rpt]
report_clock_interaction -delay_type min_max -file [file join $OUTDIR clock_interaction.rpt]
report_clock_networks  -file [file join $OUTDIR clock_networks.rpt]
report_drc            -name drc_routed -file [file join $OUTDIR drc_routed.rpt]
report_utilization    -file [file join $OUTDIR utilization_routed.rpt]
report_power          -file [file join $OUTDIR power_routed.rpt]
report_cdc            -details -file [file join $OUTDIR cdc_routed.rpt]
close_design

set bitpath [file join [get_property DIRECTORY [get_runs impl_1]] "${top}.bit"]
puts "==M4S_BIT_PATH=${bitpath}=="
puts "==M4S_BIT_EXISTS=[expr {[file exists $bitpath] ? "YES" : "NO"}]=="

file copy -force $bitpath [file join $BITDIR smartscan_npu_hdmi_raw.bit]

puts "==M4S_IMPL_OK=="
close_project
exit 0
