set bit_file {F:/Project_vivado/mandatory_core_board_validation_50mhz/bitstreams_ila_50mhz_resetfix/board_mandatory_core_test_top_ila_50mhz_resetfix_disable_icap.bit}
set ltx_file {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz_resetfix_routed_eco/mandatory_core_routed_ila_50mhz_resetfix.ltx}

open_hw
connect_hw_server
open_hw_target

set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"

set devices [get_hw_devices]
puts "HW_DEVICE_COUNT=[llength $devices]"
if {[llength $devices] != 1} {
  error "Expected exactly one JTAG device, found [llength $devices]"
}

set dev [lindex $devices 0]
puts "HW_DEVICE=$dev"
puts "HW_DEVICE_PART=[get_property PART $dev]"
if {[get_property PART $dev] ne "xc7z030"} {
  error "Refusing to program unexpected device [get_property PART $dev]"
}

current_hw_device $dev
set_property BSCAN_SWITCH_USER_MASK 0001 $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bit_file $dev
set_property PROBES.FILE $ltx_file $dev
set_property FULL_PROBES.FILE $ltx_file $dev

puts "PROGRAM_FILE=[get_property PROGRAM.FILE $dev]"
puts "PROBES_FILE=[get_property PROBES.FILE $dev]"
puts "PROGRAMMING_BEGIN"
program_hw_devices $dev
puts "PROGRAMMING_COMMAND_COMPLETE"

refresh_hw_device -update_hw_probes true $dev
set ilas [get_hw_ilas -of_objects $dev]
puts "HW_ILA_COUNT=[llength $ilas]"
foreach ila $ilas {
  puts "HW_ILA=$ila"
}

close_hw_target
disconnect_hw_server
close_hw
puts "PL_JTAG_RESETFIX_PROGRAMMING_COMPLETE"
exit
