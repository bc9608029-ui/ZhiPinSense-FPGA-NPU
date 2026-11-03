open_hw
connect_hw_server
open_hw_target
set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
set devices [get_hw_devices]
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"
puts "HW_DEVICE_COUNT=[llength $devices]"
foreach dev $devices {
    puts "HW_DEVICE=$dev"
    puts "HW_DEVICE_PART=[get_property PART $dev]"
}
if {[llength $devices] != 1} {
    error "Expected exactly one PL JTAG device"
}
if {[get_property PART [lindex $devices 0]] ne "xc7z030"} {
    error "Unexpected PL JTAG device"
}
close_hw_target
disconnect_hw_server
close_hw
puts "PS_PL_SMOKE_JTAG_VERIFY_PASS"
exit
