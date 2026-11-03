# export_edif_z030.tcl — open the xc7z030 XFFT synth DCP and write a STANDARD
# Unisim EDIF (hdi_primitives: LUT6/FDRE/DSP48E1/RAMB18E1/SRL16E/CARRY4/...) for
# the main Vivado project flow, matching the board's AI_Mate.edif pattern.
set DCP  {F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/smartscan_integration/xfft_z030/smartscan_fft_1024_z030_synth.dcp}
set EDIF {F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/smartscan_integration/netlist/smartscan_fft_1024_z030.edif}

puts "==EXP_BEGIN=="
if {![file exists $DCP]} { puts "==EXP_DCP_MISSING=="; exit 2 }
if {[catch {open_checkpoint $DCP} err]} {
  puts "==EXP_OPEN_FAIL== $err"
  exit 1
}
puts "==EXP_OPEN_OK=="
if {[catch {write_edif -force $EDIF} err]} {
  puts "==EXP_WRITE_FAIL== $err"
  exit 1
}
puts "==EXP_WRITE_OK exists=[expr {[file exists $EDIF] ? "YES" : "NO"}] =="
close_design
puts "==EXP_PASS=="
exit 0
