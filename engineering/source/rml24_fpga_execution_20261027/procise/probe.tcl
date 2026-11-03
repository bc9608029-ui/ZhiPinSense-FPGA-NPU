set f [open E:/rml24_fpga_execution_20261027/procise/commands.txt w]
puts $f [join [lsort [info commands]] "\n"]
close $f
puts "PROCISE_COMMAND_PROBE_PASS"
exit 0