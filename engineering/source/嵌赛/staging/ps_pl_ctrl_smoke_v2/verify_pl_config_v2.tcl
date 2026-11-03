open_hw
connect_hw_server
open_hw_target

set fpga_devices {}
foreach dev [get_hw_devices] {
    if {[get_property PART $dev] eq "xc7z030"} {
        lappend fpga_devices $dev
    }
}

if {[llength $fpga_devices] != 1} {
    error "Expected exactly one xc7z030 FPGA, found [llength $fpga_devices]"
}

set dev [lindex $fpga_devices 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
puts "VERIFY_DEVICE=$dev"
puts "VERIFY_PART=[get_property PART $dev]"
report_property $dev

close_hw_target
disconnect_hw_server
close_hw
puts "PL_CONFIG_PROPERTY_AUDIT_COMPLETE"
exit
