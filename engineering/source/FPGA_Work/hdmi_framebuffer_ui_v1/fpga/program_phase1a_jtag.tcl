# program_phase1a_jtag.tcl — Phase 1A: load the *_disable_icap.bit over JTAG.
#
# TEMPORARY / VOLATILE load only.  This NEVER writes Flash: a board power cycle
# reverts the PL to whatever the board's normal boot loads.
#
# Mirrors ps_pl_ctrl_smoke_resetfix/program_ps_pl_ctrl_smoke.tcl (proven on this
# board), only the bitstream path and final message differ.
#
# Run in the Vivado 2020.2 Tcl shell (Hardware Manager), with the board powered
# and the PL JTAG header (20-pin U19) connected:
#   D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode tcl -source F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/program_phase1a_jtag.tcl

set bit_file {F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit}

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
puts "HW_DEVICE=$dev"
puts "HW_DEVICE_PART=[get_property PART $dev]"
if {[get_property PART $dev] ne "xc7z030"} {
    error "Refusing to program unexpected device [get_property PART $dev]"
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
puts "HW_DEVICE_PROGRAMMED=[get_property PROGRAMMED $dev]"

close_hw_target
disconnect_hw_server
close_hw
puts "PHASE1A_JTAG_LOAD_COMPLETE"
exit
