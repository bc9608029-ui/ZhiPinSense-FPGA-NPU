set_param general.maxThreads 2
open_project E:/FPGA_Work/smartscan_prefetch_fix3_20261031/fpga/npu_base/fpai_demo_vivado.xpr
update_compile_order -fileset sources_1
reset_run synth_1
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error FIX3_SYNTH_FAILED}
puts FIX3_FINAL_SYNTH_PASS
close_project
exit
