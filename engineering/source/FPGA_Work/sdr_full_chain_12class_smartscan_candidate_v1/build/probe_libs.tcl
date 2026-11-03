set edif "F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/smartscan_integration/netlist/smartscan_fft_1024.edif"
create_project -in_memory -part xc7z030ffg676-2 probe_libs
read_edif $edif
puts "==PROBE_LIBS=="
foreach l [lsort [get_libraries]] { puts "lib: $l" }
puts "==PROBE_FILES=="
foreach f [get_files] { puts "file: [get_property FILE_TYPE $f] | [get_property LIBRARY $f] | $f" }
