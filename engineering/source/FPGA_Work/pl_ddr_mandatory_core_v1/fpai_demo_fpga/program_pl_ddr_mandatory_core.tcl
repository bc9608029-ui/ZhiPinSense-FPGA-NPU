# JTAG programming of the FMQL30TAI PL with the disable_icap bitstream.
# Adapted from the verified ps_pl_ctrl_smoke_v2 programming flow: locate the
# single xc7z030 device on the chain, program the _disable_icap.bit, and verify
# the FPGA configuration-status register bits.

set bit_file {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_disable_icap.bit}

if {![file exists $bit_file]} {
    error "Programming file not found: $bit_file"
}

open_hw
connect_hw_server
open_hw_target

set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target
puts "JTAG_TARGET=$target"
puts "JTAG_FREQUENCY=[get_property PARAM.FREQUENCY $target]"

set fpga_devices {}
foreach dev [get_hw_devices] {
    set part [get_property PART $dev]
    puts "HW_CHAIN_DEVICE=$dev PART=$part"
    if {$part eq "xc7z030"} {
        lappend fpga_devices $dev
    }
}

puts "PROGRAMMABLE_FPGA_COUNT=[llength $fpga_devices]"
if {[llength $fpga_devices] != 1} {
    error "Refusing to program: expected exactly one xc7z030 FPGA, found [llength $fpga_devices]"
}

set dev [lindex $fpga_devices 0]
current_hw_device $dev
set_property BSCAN_SWITCH_USER_MASK 0001 $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bit_file $dev
puts "PROGRAM_DEVICE=$dev"
puts "PROGRAM_PART=[get_property PART $dev]"
puts "PROGRAM_FILE=[get_property PROGRAM.FILE $dev]"
puts "PROGRAMMING_BEGIN"
program_hw_devices $dev
puts "PROGRAMMING_COMMAND_COMPLETE"
refresh_hw_device -update_hw_probes false $dev

set done_pin       [get_property REGISTER.CONFIG_STATUS.BIT14_DONE_PIN $dev]
set done_internal  [get_property REGISTER.CONFIG_STATUS.BIT13_DONE_INTERNAL_SIGNAL_STATUS $dev]
set eos_status     [get_property REGISTER.CONFIG_STATUS.BIT04_END_OF_STARTUP_\(EOS\)_STATUS $dev]
set gwe_status     [get_property REGISTER.CONFIG_STATUS.BIT06_GWE_STATUS $dev]
set crc_error      [get_property REGISTER.CONFIG_STATUS.BIT00_CRC_ERROR $dev]
set idcode_error   [get_property REGISTER.CONFIG_STATUS.BIT15_IDCODE_ERROR $dev]
set ir_done        [get_property REGISTER.IR.BIT5_DONE $dev]

puts "CONFIG_DONE_PIN=$done_pin"
puts "CONFIG_DONE_INTERNAL=$done_internal"
puts "CONFIG_EOS=$eos_status"
puts "CONFIG_GWE=$gwe_status"
puts "CONFIG_CRC_ERROR=$crc_error"
puts "CONFIG_IDCODE_ERROR=$idcode_error"
puts "CONFIG_IR_DONE=$ir_done"

if {$done_pin ne "1" || $done_internal ne "1" || $eos_status ne "1" ||
    $gwe_status ne "1" || $ir_done ne "1" || $crc_error ne "0" ||
    $idcode_error ne "0"} {
    error "FPGA configuration-status verification failed"
}

close_hw_target
disconnect_hw_server
close_hw
puts "PL_DDR_MANDATORY_CORE_PROGRAMMING_COMPLETE"
exit
