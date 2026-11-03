set edif "F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/smartscan_integration/netlist/smartscan_fft_1024.edif"
create_project -in_memory -part xc7z030ffg676-2 probe_edif
read_edif $edif
puts "==PROBE_AFTER_READ_EDIF=="
puts "designs: [lsort [get_designs]]"
puts "cells: [lsort [get_cells]]"
foreach d [get_designs] {
  puts "design $d : top=[get_property top [get_design $d]]"
}
link_design -top smartscan_fft_1024 -part xc7z030ffg676-2
puts "==PROBE_AFTER_LINK=="
puts "link cells: [llength [get_cells]]"
puts "link top: [get_property top [current_design]]"
