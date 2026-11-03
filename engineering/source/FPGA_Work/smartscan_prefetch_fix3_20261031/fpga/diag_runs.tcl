set PRJ {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/npu_base/fpai_demo_vivado.xpr}
open_project $PRJ
puts "==TOP=[get_property top [current_fileset]]=="
foreach r {synth_1 impl_1 ps_ai_processing_system7_0_0_synth_1 mig_7series_0_synth_1 clk_wiz_0_synth_1 clk_wiz_core_50_synth_1} {
  if {[get_runs -quiet $r] ne ""} {
    puts "RUN $r STATUS=[get_property STATUS [get_runs $r]] PROGRESS=[get_property PROGRESS [get_runs $r]] IS_LOCKED=[get_property IS_LOCKED [get_runs $r]] NEEDS_REFRESH=[get_property NEEDS_REFRESH [get_runs $r]]"
  } else {
    puts "RUN $r <absent>"
  }
}
close_project
