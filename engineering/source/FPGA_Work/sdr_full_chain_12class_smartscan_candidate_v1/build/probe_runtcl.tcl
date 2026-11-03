open_project F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/npu_base/fpai_demo_vivado.xpr
reset_run synth_1
set rt [get_property STEPS.SYNTH_DESIGN.TCL.PRE [get_runs synth_1]]
puts "==PROBE_RESET_DONE=="
close_project
