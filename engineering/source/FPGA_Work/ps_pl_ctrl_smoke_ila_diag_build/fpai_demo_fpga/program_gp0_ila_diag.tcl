set bit_file {F:/FPGA_Work/ps_pl_ctrl_smoke_ila_diag_build/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/ps_pl_ctrl_smoke_top_disable_icap.bit}
set ltx_file {F:/FPGA_Work/ps_pl_ctrl_smoke_ila_diag_build/fpai_demo_fpga/reports/ps_pl_ctrl_smoke_ila_diag/ps_pl_ctrl_smoke_ila_diag.ltx}

foreach required_file [list $bit_file $ltx_file] {
    if {![file exists $required_file]} {
        error "Required programming file not found: $required_file"
    }
}

open_hw
connect_hw_server
open_hw_target

set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"

set devices [get_hw_devices]
puts "HW_DEVICE_COUNT=[llength $devices]"
set fpga_devices [get_hw_devices -filter {PART == xc7z030}]
if {[llength $fpga_devices] != 1} {
    error "Expected exactly one xc7z030 JTAG device, found [llength $fpga_devices]"
}

set dev [lindex $fpga_devices 0]
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
set_property PROBES.FILE $ltx_file $dev
set_property FULL_PROBES.FILE $ltx_file $dev

puts "PROGRAM_FILE=[get_property PROGRAM.FILE $dev]"
puts "PROBES_FILE=[get_property PROBES.FILE $dev]"
puts "PROGRAMMING_BEGIN"
program_hw_devices $dev
puts "PROGRAMMING_COMMAND_COMPLETE"

refresh_hw_device -update_hw_probes true $dev
set ilas [get_hw_ilas -of_objects $dev]
puts "HW_ILA_COUNT=[llength $ilas]"
foreach ila $ilas {
    puts "HW_ILA=$ila CORE_STATUS=[get_property STATUS.CORE_STATUS $ila]"
}
puts "CONFIG_STATUS=[get_property REGISTER.CONFIG_STATUS $dev]"

if {[llength $ilas] != 1} {
    error "Expected exactly one hardware ILA after programming"
}

close_hw_target
disconnect_hw_server
close_hw
puts "GP0_ILA_DIAG_PROGRAMMING_PASS"
exit 0
