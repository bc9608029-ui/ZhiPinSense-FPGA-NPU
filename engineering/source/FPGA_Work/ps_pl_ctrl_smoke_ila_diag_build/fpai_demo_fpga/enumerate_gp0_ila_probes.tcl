set ltx_file {F:/FPGA_Work/ps_pl_ctrl_smoke_ila_diag_build/fpai_demo_fpga/reports/ps_pl_ctrl_smoke_ila_diag/ps_pl_ctrl_smoke_ila_diag.ltx}

open_hw
connect_hw_server
open_hw_target
set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target

set fpga_devices [get_hw_devices -filter {PART == xc7z030}]
if {[llength $fpga_devices] != 1} {
    error "Expected exactly one xc7z030 JTAG device, found [llength $fpga_devices]"
}
set dev [lindex $fpga_devices 0]
if {[get_property PART $dev] ne "xc7z030"} {
    error "Unexpected JTAG device [get_property PART $dev]"
}

current_hw_device $dev
set_property BSCAN_SWITCH_USER_MASK 0001 $dev
set_property PROBES.FILE $ltx_file $dev
set_property FULL_PROBES.FILE $ltx_file $dev
refresh_hw_device -update_hw_probes true $dev

set ilas [get_hw_ilas -of_objects $dev]
puts "HW_ILA_COUNT=[llength $ilas]"
if {[llength $ilas] != 1} {
    error "Expected exactly one hardware ILA"
}

set ila [lindex $ilas 0]
puts "HW_ILA=$ila"
puts "ILA_DATA_DEPTH=[get_property CONTROL.DATA_DEPTH $ila]"
set probes [get_hw_probes -of_objects $ila]
puts "HW_PROBE_COUNT=[llength $probes]"
foreach probe $probes {
    puts "HW_PROBE=$probe WIDTH=[get_property WIDTH $probe]"
}

close_hw_target
disconnect_hw_server
close_hw
puts "GP0_ILA_PROBE_ENUMERATION_PASS"
exit 0
