set frozen_dcp [lindex $argv 0]
open_checkpoint $frozen_dcp
puts "FROZEN_DCP_PROBE result=OPEN_OK cells=[llength [get_cells -hierarchical]]"
close_design
exit 0
