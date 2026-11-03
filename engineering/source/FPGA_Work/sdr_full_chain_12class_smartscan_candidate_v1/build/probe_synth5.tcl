set edif "F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/smartscan_integration/netlist/smartscan_fft_1024.edif"
set stub "F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/smartscan_integration/netlist/smartscan_fft_1024_blackbox.v"
set wrap "F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/build/probe_wrap2.v"
create_project -in_memory -part xc7z030ffg676-2 probe_synth
read_verilog -library xil_defaultlib $stub
read_verilog -library xil_defaultlib $wrap
read_edif $edif
if {[catch {synth_design -top probe_wrap2 -part xc7z030ffg676-2} serr]} {
  puts "SYNTH_FAILED_stub2: $serr"
} else {
  puts "SYNTH_OK_stub2  cells=[llength [get_cells]]"
}
