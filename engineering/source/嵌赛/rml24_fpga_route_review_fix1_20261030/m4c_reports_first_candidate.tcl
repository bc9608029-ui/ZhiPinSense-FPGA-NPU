# m4c_resume_route_smartscan.tcl — 从 placed 检查点续跑布线 + 位流 + 报告（m4 的续跑版）。
#
# 与 m4_impl_bitgen_smartscan.tcl 的区别（关键）：
#   - 不 reset_run impl_1、不 launch_runs —— 那会抹掉已完成的 place 检查点。
#   - 直接 open_checkpoint placed DCP，然后 route_design / write_bitstream / 报告。
#   - 不改任何 RTL / XDC / 约束，不放宽时序，不碰 FFT。
#
# Precondition: place_design 已完成，placed DCP 存在（m4 在 Phase 4.2 被杀时已落盘）。
# 输出：候选位流 smartscan_npu_hdmi_raw.bit + 全部报告 + M4R_* 标记。

set PRJ        {F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/npu_base/fpai_demo_vivado.xpr}
set OUTDIR     {F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/outputs/smartscan_candidate_v1/reports}
set BITDIR     {F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/outputs/smartscan_candidate_v1/bitstream}
set CDC_XDC    {F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/pl_ddr_integration_v1/cdc_async_groups.xdc}
set RUN_DIR    {F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/npu_base/fpai_demo_vivado.runs/impl_1}
set PLACED_DCP [file join $RUN_DIR pl_ddr_mandatory_core_top_combined_smartscan_placed.dcp]
set TOP        {pl_ddr_mandatory_core_top_combined_smartscan}
set BITPATH    [file join $RUN_DIR ${TOP}.bit]

file mkdir $OUTDIR
file mkdir $BITDIR

# fail-closed: placed 检查点必须在（否则无从续跑）
if {![file exists $PLACED_DCP]} {
  puts "==M4R_PLACED_DCP_MISSING== $PLACED_DCP"
  exit 1
}
puts "==M4R_PLACED_DCP_OK size=[file size $PLACED_DCP]=="

open_project $PRJ
puts "==M4R_OPEN_OK top=[get_property top [current_fileset]]=="

# CDC XDC 仍在项目约束集内（与 m4 相同 fail-closed 守卫，确认约束未被改动）
if {![file exists $CDC_XDC]} {
  puts "==M4R_CDC_XDC_MISSING== $CDC_XDC"
  close_project
  exit 1
}
set cdc_active 0
foreach f [get_files -of_objects [get_filesets constrs_1]] {
  if {[string equal $f $CDC_XDC]} { set cdc_active 1 }
}
if {!$cdc_active} {
  puts "==M4R_CDC_XDC_NOT_ACTIVE== $CDC_XDC"
  close_project
  exit 1
}
puts "==M4R_CDC_XDC_ACTIVE=[file tail $CDC_XDC]=="

# 续跑：从 placed 检查点打开（不 reset_run / launch_runs）
open_checkpoint $PLACED_DCP
puts "==M4R_PLACED_OPENED=="

route_design
puts "==M4R_ROUTE_DONE=="

write_checkpoint -force [file join $OUTDIR routed_before_signoff.dcp]
# 时序口径（审计 #1）：WNS/WHS=最差单路径，TNS/THS=所有失败路径负裕量之和
set setup_paths [get_timing_paths -setup -max_paths 1]
set hold_paths [get_timing_paths -hold -max_paths 1]
if {[llength $setup_paths] != 1 || [llength $hold_paths] != 1} {error "timing path query missing"}
set wns [get_property SLACK $setup_paths]
set whs [get_property SLACK $hold_paths]
# Authoritative TNS/THS are in report_timing_summary.
# 报告（时序 min_max 含 setup+hold；其余同 m4）
report_timing_summary   -delay_type min_max -max_paths 10 -file [file join $OUTDIR timing_summary_routed.rpt]
report_clock_interaction -delay_type min_max -file [file join $OUTDIR clock_interaction.rpt]
report_clock_networks   -file [file join $OUTDIR clock_networks.rpt]
report_drc              -name drc_routed -file [file join $OUTDIR drc_routed.rpt]
report_utilization      -file [file join $OUTDIR utilization_routed.rpt]
report_power            -file [file join $OUTDIR power_routed.rpt]
if {[catch {report_cdc -details -file [file join $OUTDIR cdc_routed.rpt]} err]} {
  puts "==M4R_REPORT_CDC_FAIL err=${err}=="
}

report_route_status -file [file join $OUTDIR route_status.rpt]
check_timing -verbose -file [file join $OUTDIR check_timing.rpt]
if {![string is double -strict $wns] || ![string is double -strict $whs]} {error "invalid timing result"}
if {$wns < 0.0 || $whs < 0.0} {error "timing failed - checkpoint and reports preserved - no bitstream"}
# Review route completeness, unconstrained paths, CDC and DRC before enabling bitgen.
puts "==M4R_REPORT_REVIEW_REQUIRED_NO_BITSTREAM=="
close_project
exit 2
# 复制候选位流到输出目录（与 m4 相同落点，m5 Procise 从此读取）
file copy -force $BITPATH [file join $BITDIR smartscan_npu_hdmi_raw.bit]
puts "==M4R_BIT_COPIED=[file exists [file join $BITDIR smartscan_npu_hdmi_raw.bit]]=="

puts "==M4R_IMPL_OK=="
close_project
exit 0
