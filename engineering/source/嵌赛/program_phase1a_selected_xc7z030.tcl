set bit_file {F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit}
if {![file exists $bit_file]} { error "Programming file not found: $bit_file" }

open_hw
connect_hw_server
open_hw_target
set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"

set matches {}
foreach d [get_hw_devices] {
    puts "DISCOVERED_DEVICE=$d PART=[get_property PART $d]"
    if {[get_property PART $d] eq "xc7z030"} { lappend matches $d }
}
if {[llength $matches] != 1} {
    error "Expected exactly one xc7z030 device, found [llength $matches]"
}
set dev [lindex $matches 0]
current_hw_device $dev
set_property BSCAN_SWITCH_USER_MASK 0001 $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bit_file $dev
puts "PROGRAM_FILE=[get_property PROGRAM.FILE $dev]"
puts "PROGRAMMING_BEGIN"
program_hw_devices $dev
puts "PROGRAMMING_COMMAND_COMPLETE"
refresh_hw_device -update_hw_probes false $dev
puts "HW_DEVICE_PROGRAMMED=[get_property PROGRAMMED $dev]"
if {![get_property PROGRAMMED $dev]} { error "xc7z030 did not report PROGRAMMED=true" }
close_hw_target
disconnect_hw_server
close_hw
puts "PHASE1A_JTAG_LOAD_COMPLETE"
exit
