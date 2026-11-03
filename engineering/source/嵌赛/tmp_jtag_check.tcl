open_hw_manager
connect_hw_server -url localhost:3121 -allow_non_jtag
set targets [get_hw_targets]
puts "JTAG_TARGET_COUNT=[llength $targets]"
foreach t $targets {
    puts "JTAG_TARGET=$t"
    if {[catch {open_hw_target $t} err]} {
        puts "OPEN_TARGET_ERROR=$err"
    } else {
        set devs [get_hw_devices]
        puts "JTAG_DEVICE_COUNT=[llength $devs]"
        foreach d $devs { puts "JTAG_DEVICE=$d PART=[get_property PART $d]" }
        close_hw_target
    }
}
disconnect_hw_server
close_hw_manager
exit
