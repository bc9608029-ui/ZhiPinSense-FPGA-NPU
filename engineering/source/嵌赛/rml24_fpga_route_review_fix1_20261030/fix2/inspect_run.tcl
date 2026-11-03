open_project {F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/npu_base/fpai_demo_vivado.xpr}
puts "ACTUAL_IMPL_STATUS=[get_property STATUS [get_runs impl_1]]"
puts "ACTUAL_IMPL_PROGRESS=[get_property PROGRESS [get_runs impl_1]]"
report_property [get_runs impl_1]
close_project
exit
