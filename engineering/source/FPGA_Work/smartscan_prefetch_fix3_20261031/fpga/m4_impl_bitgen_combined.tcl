# m4_impl_bitgen_combined.tcl — 合并位流第 2 步：实现 + 写位流 + 从最终 routed DCP 一次性生成全部报告。
#
# 前置：m3_synth_combined.tcl 已成功（synth_1 checkpoint 存在）。本脚本复用该
# checkpoint 做 impl_1 → write_bitstream（FMSH 的 implementation_* 与 write_bitstream
# 前后钩子会自动触发）。完成后从同一 routed DCP 生成 timing/DRC/clock/CDC 报告。

set PRJ     {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/npu_base/fpai_demo_vivado.xpr}
set OUTDIR  {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/outputs/smoke_v1/reports}
set BITDIR  {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/outputs/smoke_v1/bitstream}
set CDC_XDC {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/pl_ddr_integration_v1/cdc_async_groups.xdc}

file mkdir $OUTDIR
file mkdir $BITDIR

open_project $PRJ
puts "==M4_OPEN_OK top=[get_property top [current_fileset]]=="

# CDC 异步时钟组隔离已在 constrs_1 内（pl_ddr_integration_v1/cdc_async_groups.xdc，已删
# 失效的 frame_to_ps 第 5 组）。这里只做 fail-closed 校验：文件须存在且确在活动约束集中，
# 否则不启动实现（否则 Vivado 会把互异步域路径当合法 inter-clock 路径计时，复现 9344 hold）。
if {![file exists $CDC_XDC]} {
  puts "==M4_CDC_XDC_MISSING== $CDC_XDC"
  close_project
  exit 1
}
set cdc_active 0
foreach f [get_files -of_objects [get_filesets constrs_1]] {
  if {[string equal $f $CDC_XDC]} { set cdc_active 1 }
}
if {!$cdc_active} {
  puts "==M4_CDC_XDC_NOT_ACTIVE== $CDC_XDC"
  close_project
  exit 1
}
puts "==M4_CDC_XDC_ACTIVE=[file tail $CDC_XDC]=="

# 复用已完成的 synth_1 / OOC run，仅重置并重跑 impl_1 到 write_bitstream。
reset_run impl_1
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1

set st [get_property STATUS [get_runs impl_1]]
set pr [get_property PROGRESS [get_runs impl_1]]
puts "==M4_IMPL_STATUS=${st}=="
puts "==M4_IMPL_PROGRESS=${pr}=="

if {$pr ne "100%"} {
  puts "==M4_IMPL_FAILED== status=${st} see fpga/npu_base/fpai_demo_vivado.runs/impl_1/runme.log"
  close_project
  exit 1
}

# 从最终 routed DCP 一次性生成报告
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

# 位流输出路径（raw .bit，尚未经 Procise -disable_icap）
set bitpath [file join [get_property DIRECTORY [get_runs impl_1]] "${top}.bit"]
puts "==M4_BIT_PATH=${bitpath}=="
puts "==M4_BIT_EXISTS=[expr {[file exists $bitpath] ? "YES" : "NO"}]=="

# 复制 raw .bit 到交付目录（临时名，待 Procise 后改名）
file copy -force $bitpath [file join $BITDIR combined_npu_hdmi_raw.bit]

puts "==M4_IMPL_OK=="
close_project
exit 0
