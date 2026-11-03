set ltx_file {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz/mandatory_core_routed_ila_50mhz.ltx}

open_hw
connect_hw_server
open_hw_target

set target [current_hw_target]
puts "HW_TARGET=$target"
if {![catch {set old_freq [get_property PARAM.FREQUENCY $target]}]} {
  puts "JTAG_FREQUENCY_BEFORE=$old_freq"
}
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_FREQUENCY_AFTER=[get_property PARAM.FREQUENCY $target]"

set dev [lindex [get_hw_devices] 0]
current_hw_device $dev
set_property BSCAN_SWITCH_USER_MASK 0001 $dev
set_property PROBES.FILE $ltx_file $dev
set_property FULL_PROBES.FILE $ltx_file $dev
refresh_hw_device -update_hw_probes true $dev

set ilas [get_hw_ilas -of_objects $dev]
puts "HW_ILA_COUNT=[llength $ilas]"
foreach ila $ilas {
  puts "HW_ILA=$ila"
}

close_hw_target
disconnect_hw_server
close_hw
puts "LOW_JTAG_DEBUG_HUB_RETRY_COMPLETE"
exit
