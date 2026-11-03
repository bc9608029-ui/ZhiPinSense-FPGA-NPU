set edif "F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/smartscan_integration/netlist/smartscan_fft_1024.edif"
create_project -in_memory -part xc7z030ffg676-2 probe_edif
read_edif $edif
puts "==PROBE_LINK_TOP=="
if {[catch {link_design -top smartscan_fft_1024 -part xc7z030ffg676-2} lerr]} {
  puts "LINK_FAILED: $lerr"
} else {
  puts "LINK_OK cells=[llength [get_cells]] top=[get_property top [current_design]]"
}
