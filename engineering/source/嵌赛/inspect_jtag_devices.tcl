open_hw
connect_hw_server
open_hw_target
set devices [get_hw_devices]
puts "HW_DEVICE_COUNT=[llength $devices]"
set i 0
foreach d $devices {
    puts "DEVICE_INDEX=$i NAME=$d PART=[get_property PART $d] PROGRAMMED=[get_property PROGRAM.FILE $d]"
    incr i
}
close_hw_target
disconnect_hw_server
close_hw
exit
