open_project F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/npu_base/fpai_demo_vivado.xpr
foreach f [get_files] {
  set bn [file tail $f]
  if {$bn eq "AI_Mate_stub.v" || $bn eq "AI_Mate.edif"} {
    puts "FILE: $bn"
    puts "  is_enabled=[get_property is_enabled $f]"
    puts "  used_in_synthesis=[get_property used_in_synthesis $f]"
    puts "  used_in_implementation=[get_property used_in_implementation $f]"
    puts "  is_auto_disabled=[get_property is_auto_disabled $f]"
    puts "  file_type=[get_property file_type $f]"
    puts "  library=[get_property library $f]"
  }
}
close_project
