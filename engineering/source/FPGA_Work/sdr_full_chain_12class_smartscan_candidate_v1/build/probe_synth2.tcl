set edif "F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/smartscan_integration/netlist/smartscan_fft_1024.edif"
set wrap "F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/build/probe_wrap.v"
create_project -in_memory -part xc7z030ffg676-2 probe_synth
read_verilog -library xil_defaultlib $wrap
read_edif -library work $edif
if {[catch {synth_design -top probe_wrap -part xc7z030ffg676-2} serr]} {
  puts "SYNTH_FAILED_lib=work : $serr"
} else {
  puts "SYNTH_OK_lib=work"
}
