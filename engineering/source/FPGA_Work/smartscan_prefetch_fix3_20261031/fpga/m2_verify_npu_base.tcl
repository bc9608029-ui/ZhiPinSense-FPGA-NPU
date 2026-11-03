# m2_verify_npu_base.tcl — 打开拷贝后的 NPU 基座工程，验证路径重定位 + BD + 文件集完整。
set PRJ {E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/npu_base/fpai_demo_vivado.xpr}
open_project $PRJ
puts "==OPEN_OK=="
puts "==PART=[get_property PART [current_project]]=="
puts "==TOP=[get_property TOP [current_fileset]]=="
puts "==FILES_TOTAL=[llength [get_files]]=="
puts "==SRC_FILES=[llength [get_files -of_objects [get_filesets sources_1]]]== "
puts "==CONSTR_FILES=[llength [get_files -of_objects [get_filesets constrs_1]]]=="
puts "==BD_FILES=[llength [get_files -filter {FILE_TYPE == Block Designs}]]=="
# 关键文件是否存在（Mandatory Core RTL + AI_Mate.edif + ps_ai_peripheral）
foreach f {pl_ddr_mandatory_core_top.sv ps_ai_peripheral.sv AI_Mate.edif ps_ai.bd} {
  set hit [get_files -quiet "*${f}"]
  puts "==HAS_${f}=[expr {[llength $hit]>0 ? "YES" : "NO"}] =="
}
close_project
puts "==VERIFY_DONE=="
