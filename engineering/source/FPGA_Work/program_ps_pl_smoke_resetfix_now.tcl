set bit_file {F:/FPGA_Work/artifacts/ps_pl_ctrl_smoke_resetfix_20260928/ps_pl_ctrl_smoke_top_disable_icap.bit}

if {![file exists $bit_file]} {
    error "Programming file not found: $bit_file"
}

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
set part [get_property PART $dev]
puts "HW_DEVICE=$dev"
puts "HW_DEVICE_PART=$part"
if {$part ne "xc7z030"} {
    error "Refusing to program unexpected device $part"
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
puts "CONFIG_STATUS=[get_property REGISTER.CONFIG_STATUS $dev]"

close_hw_target
disconnect_hw_server
close_hw
puts "PS_PL_CTRL_SMOKE_RESETFIX_PROGRAMMING_PASS"
exit
