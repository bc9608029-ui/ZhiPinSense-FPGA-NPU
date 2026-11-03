# m3_synth_combined.tcl — 合并位流第 1 步：综合（合成顶层=pl_ddr_mandatory_core_top_combined）
#
# 在已拷贝的 NPU 基座工程（fpga/npu_base/fpai_demo_vivado.xpr）上：
#   1) 追加三个新 RTL 文件（fb_read_720p.sv / ps_ai_peripheral_combined.sv /
#      pl_ddr_mandatory_core_top_combined.sv）
#   2) 把合成顶层从官方 pl_ddr_mandatory_core_top 切到 *_combined
#   3) 只跑综合，快速暴露 RTL/端口/依赖错误（不做 place/route）
#
# 全部输出写入合并工程，绝不改写来源工程。
#
# 恢复策略：上一轮失败会在 synth_1（顶层综合）与其 OOC 依赖 ps_ai_processing_system7_0_0_synth_1
# （PS7 黑盒桩综合）上留下 ERROR/脏状态；launch_runs 会拒绝在非 fresh 的 run 上执行。
# 因此先显式 reset 这两个 run 再 launch。-jobs 1 对齐 NPU 基座已验证脚本（run_impl_*.tcl
# 原文：-jobs 1 以避免早前 OOM 内存峰值），并规避 2018.3 并行 launch 偶发的 run 脚本空 -source。

set PRJ    {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/npu_base/fpai_demo_vivado.xpr}
set RTL    {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/npu_base/rtl}
set INTEG  {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/pl_ddr_integration_v1/rtl}

open_project $PRJ

puts "==OPEN_OK=="

# 追加新文件（幂等：add_files 对已存在文件不会重复添加）
add_files -norecurse [list \
  [file join $RTL   display fb_read_720p.sv] \
  [file join $RTL   ps_ai_peripheral_combined.sv] \
  [file join $INTEG pl_ddr_mandatory_core_top_combined.sv] \
]

set_property top pl_ddr_mandatory_core_top_combined [current_fileset]
update_compile_order -fileset sources_1

puts "==TOP=[get_property top [current_fileset]]=="
foreach f [list \
  [file join $RTL   display fb_read_720p.sv] \
  [file join $RTL   ps_ai_peripheral_combined.sv] \
  [file join $INTEG pl_ddr_mandatory_core_top_combined.sv] \
] {
  puts "==SRC_EXISTS=[expr {[file exists $f] ? "YES" : "NO"}] $f=="
}

# 显式清掉可能残留的脏状态：PS7 黑盒桩 OOC 综合 + 顶层综合。
# （其余 OOC run：mig_7series_0 / clk_wiz_0 / clk_wiz_core_50 等已完成 100%，不动，复用。）
if {[get_runs -quiet ps_ai_processing_system7_0_0_synth_1] ne ""} {
  reset_run ps_ai_processing_system7_0_0_synth_1
  puts "==RESET_PS7_OOC=done=="
}
reset_run synth_1
puts "==RESET_SYNTH_1=done=="

# 综合（单步，快速反馈；出错脚本在此中断）
launch_runs synth_1 -jobs 1
wait_on_run synth_1

set st [get_property STATUS   [get_runs synth_1]]
set pr [get_property PROGRESS [get_runs synth_1]]
puts "==SYNTH_STATUS=${st}=="
puts "==SYNTH_PROGRESS=${pr}=="
if {$pr ne "100%"} {
  puts "==SYNTH_FAILED== status=${st} see fpga/npu_base/fpai_demo_vivado.runs/synth_1/runme.log"
  close_project
  exit 1
}
puts "==M3_SYNTH_OK=="
close_project
exit 0
