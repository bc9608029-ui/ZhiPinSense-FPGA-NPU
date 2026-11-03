set ltx_file {F:/FPGA_Work/ps_pl_ctrl_smoke_ila_diag_build/fpai_demo_fpga/reports/ps_pl_ctrl_smoke_ila_diag/ps_pl_ctrl_smoke_ila_diag.ltx}
set capture_dir {F:/FPGA_Work/ps_pl_ctrl_smoke_ila_diag_build/fpai_demo_fpga/captures}
set csv_file [file join $capture_dir gp0_read_diag.csv]
file mkdir $capture_dir

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
if {[llength $ilas] != 1} {
    error "Expected exactly one hardware ILA"
}
set ila [lindex $ilas 0]
set probes [get_hw_probes dbg_gp0_read -of_objects $ila]
if {[llength $probes] != 1 || [get_property WIDTH [lindex $probes 0]] != 141} {
    error "Expected one 141-bit dbg_gp0_read probe"
}
set probe [lindex $probes 0]

set_property CONTROL.DATA_DEPTH 1024 $ila
set_property CONTROL.TRIGGER_POSITION 512 $ila
set_property CONTROL.TRIGGER_CONDITION AND $ila

# dbg_gp0_read[105] is PS M_AXI_GP0 ARVALID.  The string is written MSB-first.
set trigger_bits [string repeat x 141]
set trigger_bits [string replace $trigger_bits [expr {140 - 105}] [expr {140 - 105}] 1]
set trigger_value "eq141'b$trigger_bits"
set_property TRIGGER_COMPARE_VALUE $trigger_value $probe
puts "ILA_TRIGGER=dbg_gp0_read\[105\]==1"
puts "ILA_TRIGGER_COMPARE_VALUE=$trigger_value"

run_hw_ila $ila
puts "GP0_ILA_ARMED"
flush stdout
wait_on_hw_ila $ila
puts "GP0_ILA_TRIGGERED"

set data [upload_hw_ila_data $ila]
write_hw_ila_data -force -csv_file $csv_file $data
puts "GP0_ILA_CAPTURE_CSV=$csv_file"

close_hw_target
disconnect_hw_server
close_hw
puts "GP0_ILA_CAPTURE_PASS"
exit 0
