# probe_read_edif.tcl — cheap probe: can this Vivado read + link the migrated FMSH EDIF
# against the board part xc7z030ffg676-2?  Run in batch; prints a PASS/FAIL token.
set EDIF {E:/FPGA_Work/smartscan_prefetch_fix3_20261031/fpga/smartscan_integration/netlist/smartscan_fft_1024.edif}

puts "==PROBE_BEGIN=="
if {![file exists $EDIF]} { puts "==PROBE_EDIF_MISSING=="; exit 2 }

if {[catch {read_edif $EDIF} err]} {
  puts "==PROBE_READ_EDIF_FAIL== $err"
  exit 1
}
puts "==PROBE_READ_EDIF_OK=="

if {[catch {link_design -part xc7z030ffg676-2 -top smartscan_fft_1024} err]} {
  puts "==PROBE_LINK_FAIL== $err"
  exit 1
}
puts "==PROBE_LINK_OK=="

if {[catch {report_utilization -quiet} err]} {
  puts "==PROBE_UTIL_FAIL== $err"
} else {
  puts "==PROBE_UTIL_OK=="
}
puts "==PROBE_PASS=="
exit 0
