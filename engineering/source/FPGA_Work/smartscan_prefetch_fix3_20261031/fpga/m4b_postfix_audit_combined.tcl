# m4b_postfix_audit_combined.tcl — 组合位流 post-fix 例外覆盖审计（任务 39e5 最终阶段）。
#
# 前置：m4_impl_bitgen_combined.tcl 已成功（impl_1 routed，已含 set_false_path gp_clk<->cam_clk）。
# 本脚本不重跑实现，只从最终 routed DCP 一次性生成「例外覆盖审计」所需的报告：
#   1) report_exceptions 详细清单（枚举全部 set_false_path / 其他例外及其起终点覆盖）；
#   2) gp_clk <-> clk_74m25 这一对被 false path 覆盖的起点/终点/路径数量（用于与 pre-fix 324 对比）；
#   3) report_cdc -details（确认无未处理严重 CDC）。
# 全部输出到 outputs/smoke_v1/reports/（post-fix 子目录），与 pre-fix reports_pre_fix/ 对照。

set PRJ     {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/npu_base/fpai_demo_vivado.xpr}
set OUTDIR  {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/outputs/smoke_v1/reports_postfix}

file mkdir $OUTDIR

open_project $PRJ
open_run impl_1

# --- 1) 例外清单 ---
report_exceptions -file [file join $OUTDIR exceptions_routed.rpt]

# --- 2) gp_clk <-> cam_clk 被裁路径的起点/终点枚举 ---
# 方向 A：gp_clk -> cam_clk（pre-fix 290 failing）
# 方向 B：cam_clk -> gp_clk（pre-fix 34 failing）
foreach {dir fromclk toclk} {
  A {clk_out1_clk_wiz_0} {clk_74m25}
  B {clk_74m25} {clk_out1_clk_wiz_0}
} {
  set rpt [file join $OUTDIR "false_path_${dir}_endpoints.rpt"]
  set f [open $rpt w]
  # 用 report_timing 显式列出这对时钟的全部路径（含被 false path 裁掉的）；
  # -max_paths 拉满、-nworst 1 每条路径只取最坏一条，足以枚举起点/终点集合。
  puts $f "== DIR ${dir}: ${fromclk} -> ${toclk} =="
  set paths [get_timing_paths -from [get_clocks ${fromclk}] -to [get_clocks ${toclk}] -max_paths 1000000 -nworst 1 -setup]
  puts $f "PATH_COUNT=[llength $paths]"
  set starts {}
  set ends {}
  foreach p $paths {
    lappend starts [get_property STARTPOINT_PIN $p]
    lappend ends   [get_property ENDPOINT_PIN   $p]
  }
  set starts [lsort -unique $starts]
  set ends   [lsort -unique $ends]
  puts $f "STARTPOINT_COUNT=[llength $starts]"
  foreach s $starts { puts $f "START $s" }
  puts $f "ENDPOINT_COUNT=[llength $ends]"
  foreach e $ends { puts $f "END $e" }
  close $f
  puts "==M4B_DIR_${dir}_PATHS=[llength $paths]_STARTS=[llength $starts]_ENDS=[llength $ends]=="
}

# --- 3) 详细 CDC ---
report_cdc -details -file [file join $OUTDIR cdc_routed.rpt]

# --- 4) 再出一份 timing summary，确认 post-fix 只剩冻结 1GHz pulse-width ---
report_timing_summary -delay_type min_max -max_paths 10 -file [file join $OUTDIR timing_summary_routed.rpt]
report_clock_interaction -delay_type min_max -file [file join $OUTDIR clock_interaction.rpt]

close_design
close_project
puts "==M4B_AUDIT_OK=="
exit 0
