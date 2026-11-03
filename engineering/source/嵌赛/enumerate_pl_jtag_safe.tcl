open_hw
connect_hw_server
open_hw_target

set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"

set devices [get_hw_devices]
puts "HW_DEVICE_COUNT=[llength $devices]"
foreach dev $devices {
    puts "HW_DEVICE=$dev"
    puts "HW_DEVICE_PART=[get_property PART $dev]"
    if {[lsearch -exact [list_property $dev] PROGRAMMED] >= 0} {
        puts "HW_DEVICE_PROGRAMMED=[get_property PROGRAMMED $dev]"
    }
    if {[lsearch -exact [list_property $dev] REGISTER.CONFIG_STATUS.BIT17_DONE] >= 0} {
        puts "HW_DEVICE_DONE=[get_property REGISTER.CONFIG_STATUS.BIT17_DONE $dev]"
    }
}

close_hw_target
disconnect_hw_server
close_hw
puts "PL_JTAG_ENUMERATION_COMPLETE"
exit
