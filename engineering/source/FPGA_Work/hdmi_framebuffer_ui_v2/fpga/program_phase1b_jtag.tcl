# program_phase1b_jtag.tcl — Phase 1B/1C/2/3: load the *_disable_icap.bit over JTAG.
#
# TEMPORARY / VOLATILE load only.  This NEVER writes Flash: a board power cycle
# reverts the PL to whatever the board's normal boot loads.
#
# The JTAG chain has TWO devices (arm_dap_0 = the PS DAP, plus xc7z030_1 = the
# FPGA).  This script enumerates every device and programs ONLY the one whose
# PART matches xc7z030, ignoring the DAP.  It aborts if the xc7z030 count is not
# exactly one, so it can never program the wrong device.
#
# Run in the Vivado 2020.2 Tcl shell (Hardware Manager), with the board powered
# and the PL JTAG header (20-pin U19) connected:
#   D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode tcl -source F:/FPGA_Work/hdmi_framebuffer_ui_v2/fpga/program_phase1b_jtag.tcl

set bit_file {F:/FPGA_Work/hdmi_framebuffer_ui_v2/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit}

if {![file exists $bit_file]} {
    error "Programming file not found: $bit_file"
}

open_hw
connect_hw_server
open_hw_target

set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"

# Enumerate ALL JTAG devices, then keep only the FPGA (PART == xc7z030).  The
# chain's arm_dap_0 (PS DAP) must be ignored, not counted as the target.
set all_devices [get_hw_devices]
puts "HW_DEVICE_COUNT=[llength $all_devices]"
set fpga_devices {}
foreach d $all_devices {
    set part [get_property PART $d]
    puts "HW_DEVICE=$d PART=$part"
    if {[string match "*xc7z030*" $part]} {
        lappend fpga_devices $d
    }
}

puts "FPGA_DEVICE_COUNT=[llength $fpga_devices]"
if {[llength $fpga_devices] != 1} {
    error "Expected exactly one xc7z030 device, found [llength $fpga_devices]"
}

set dev [lindex $fpga_devices 0]
puts "PROGRAMMING_PART=[get_property PART $dev]"

current_hw_device $dev
set_property BSCAN_SWITCH_USER_MASK 0001 $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bit_file $dev
puts "PROGRAM_FILE=[get_property PROGRAM.FILE $dev]"
puts "PROGRAMMING_BEGIN"
program_hw_devices $dev
puts "PROGRAMMING_COMMAND_COMPLETE"
refresh_hw_device -update_hw_probes false $dev

# Done-check: use the real DONE status register, NOT the (often stale) PROGRAMMED
# property.  REGISTER.IR.BIT5_DONE == 1 means configuration completed successfully.
set done [get_property REGISTER.IR.BIT5_DONE $dev]
puts "HW_DEVICE_DONE=$done"
if {$done != 1} {
    error "Configuration DONE flag not set (REGISTER.IR.BIT5_DONE=$done)"
}

close_hw_target
disconnect_hw_server
close_hw
puts "PHASE1B_JTAG_LOAD_COMPLETE"
exit
