set bit_file {C:/Users/shado/AppData/Local/Temp/codex_ps_pl_smoke/ps_pl_ctrl_smoke_top_disable_icap.bit}
if {![file exists $bit_file]} {
    error "Programming file not found: $bit_file"
}

open_hw
connect_hw_server
open_hw_target
set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
set devices [get_hw_devices]
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"
puts "HW_DEVICE_COUNT=[llength $devices]"
if {[llength $devices] != 1} {
    error "Expected exactly one PL JTAG device"
}
set dev [lindex $devices 0]
puts "HW_DEVICE=$dev"
puts "HW_DEVICE_PART=[get_property PART $dev]"
if {[get_property PART $dev] ne "xc7z030"} {
    error "Refusing to program unexpected PL JTAG device"
}
current_hw_device $dev
set_property BSCAN_SWITCH_USER_MASK 0001 $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bit_file $dev
puts "PROGRAM_FILE=[get_property PROGRAM.FILE $dev]"
puts "PROGRAMMING_BEGIN"
program_hw_devices $dev
puts "PROGRAMMING_COMMAND_COMPLETE"
refresh_hw_device -update_hw_probes false $dev
close_hw_target
disconnect_hw_server
close_hw
puts "PS_PL_CTRL_SMOKE_PROGRAMMING_PASS"
exit
