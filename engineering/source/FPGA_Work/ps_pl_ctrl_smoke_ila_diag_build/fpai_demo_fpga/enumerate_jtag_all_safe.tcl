open_hw
connect_hw_server
open_hw_target

set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"

set devices [get_hw_devices]
puts "HW_DEVICE_COUNT=[llength $devices]"
foreach dev $devices {
    set part [get_property PART $dev]
    set programmed "N/A"
    catch {set programmed [get_property PROGRAMMED $dev]}
    puts "HW_DEVICE=$dev PART=$part PROGRAMMED=$programmed"
}

close_hw_target
disconnect_hw_server
close_hw
puts "JTAG_SAFE_ENUMERATION_PASS"
exit 0
