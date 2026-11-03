open_hw
connect_hw_server
open_hw_target

set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_TARGET=$target"
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"

set all_devices [get_hw_devices]
puts "HW_CHAIN_DEVICE_COUNT=[llength $all_devices]"
set fpga_devices {}
foreach dev $all_devices {
    set part [get_property PART $dev]
    puts "HW_CHAIN_DEVICE=$dev PART=$part"
    if {$part eq "xc7z030"} {
        lappend fpga_devices $dev
    }
}

puts "PROGRAMMABLE_FPGA_COUNT=[llength $fpga_devices]"
if {[llength $fpga_devices] != 1} {
    error "Expected exactly one xc7z030 FPGA, found [llength $fpga_devices]"
}

set fpga [lindex $fpga_devices 0]
puts "PROGRAMMABLE_FPGA=$fpga"

close_hw_target
disconnect_hw_server
close_hw
puts "PL_JTAG_ENUMERATION_V2_COMPLETE"
exit
