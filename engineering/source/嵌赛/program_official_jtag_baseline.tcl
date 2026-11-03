set bit_file {F:/FPGA_Work/official_jtag_baseline/ai7030_top_disable_icap.bit}

open_hw
connect_hw_server
open_hw_target
set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target

set devices [get_hw_devices -filter {PART == xc7z030}]
if {[llength $devices] != 1} {
    error "Expected one xc7z030, found [llength $devices]"
}
set dev [lindex $devices 0]
current_hw_device $dev
set_property PROGRAM.FILE $bit_file $dev
program_hw_devices $dev
refresh_hw_device -update_hw_probes false $dev
puts "OFFICIAL_JTAG_PROGRAM_PASS"

close_hw_target
disconnect_hw_server
close_hw
exit 0
