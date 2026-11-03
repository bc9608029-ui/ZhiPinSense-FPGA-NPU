# diag_clocks.tcl — 综合后时钟诊断（只读，不改任何 run）。
#
# 用途：打开已完成的 synth_1，列出合并设计中所有时钟的自动命名/主从关系，
# 用于把 cdc_async_groups.xdc 的异步组写成与真实层次完全一致（不猜名字）。
# 输出到 build/ 下，供 m4 前人工核对。

set PRJ {F:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/npu_base/fpai_demo_vivado.xpr}
set OUT {F:/FPGA_Work/sdr_full_chain_12class_combined_v1/build/diag_clocks.txt}

open_project $PRJ

if {[get_runs -quiet synth_1] eq ""} {
  puts "==NO_SYNTH_RUN=="
  close_project
  exit 1
}
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
  puts "==SYNTH_NOT_DONE status=[get_property STATUS [get_runs synth_1]]=="
  close_project
  exit 1
}

open_run synth_1
set ch [open $OUT w]
puts $ch "=== report_clocks ==="
puts $ch [report_clocks -return_string]
puts $ch "=== report_clock_interaction (summary) ==="
puts $ch [report_clock_interaction -return_string]
close $ch
close_design

puts "==CLOCK_DIAG_WRITTEN== $OUT"
close_project
exit 0
