open_hw
connect_hw_server
open_hw_target

set devices [get_hw_devices]
puts "HW_DEVICE_COUNT=[llength $devices]"
foreach dev $devices {
  puts "HW_DEVICE=$dev"
  puts "HW_DEVICE_PART=[get_property PART $dev]"
}

close_hw_target
disconnect_hw_server
close_hw
puts "PL_JTAG_ENUMERATION_COMPLETE"
exit
