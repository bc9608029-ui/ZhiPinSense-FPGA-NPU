set_param general.maxThreads 2
foreach variant {original fixed} {
  create_project -in_memory -part xc7z030ffg676-2
  if {$variant eq "original"} {set src original.sv} else {set src smart_scan_psd_buffers.sv}
  read_verilog -sv $src
  synth_design -top smart_scan_psd_buffers -part xc7z030ffg676-2 -mode out_of_context
  report_utilization -hierarchical -file ${variant}_utilization.rpt
  set brams [llength [get_cells -hier -filter {REF_NAME =~ RAMB*}]]
  puts "BRAM_COMPARISON variant=$variant bram_cells=$brams"
  if {$variant eq "fixed" && $brams == 0} {error "fixed read port did not infer BRAM"}
  close_project
}
exit
