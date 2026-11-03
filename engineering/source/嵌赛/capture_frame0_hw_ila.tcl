set ltx_file {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz/mandatory_core_routed_ila_50mhz.ltx}
set csv_file {hardware_capture_frame0.csv}

open_hw
connect_hw_server
open_hw_target
set target [current_hw_target]
set_property PARAM.FREQUENCY 1000000 $target

set dev [lindex [get_hw_devices] 0]
current_hw_device $dev
set_property BSCAN_SWITCH_USER_MASK 0001 $dev
set_property PROBES.FILE $ltx_file $dev
set_property FULL_PROBES.FILE $ltx_file $dev
refresh_hw_device -update_hw_probes true $dev

set ila [lindex [get_hw_ilas -of_objects $dev] 0]
if {$ila eq ""} {
  error "No hardware ILA detected"
}

set_property CONTROL.DATA_DEPTH 1024 $ila
set_property CONTROL.TRIGGER_POSITION 0 $ila
set_property CONTROL.TRIGGER_CONDITION AND $ila
set_property CONTROL.CAPTURE_MODE BASIC $ila
set_property CONTROL.CAPTURE_CONDITION AND $ila

set frame_start_probe [get_hw_probes m_frame_start -of_objects $ila]
set write_valid_probe [get_hw_probes m_write_valid -of_objects $ila]
set_property TRIGGER_COMPARE_VALUE {eq1'b1} $frame_start_probe
set_property CAPTURE_COMPARE_VALUE {eq1'b1} $write_valid_probe

run_hw_ila $ila
puts "ILA_ARMED_PRESS_AND_RELEASE_PL_KEY1"
flush stdout
wait_on_hw_ila $ila
puts "ILA_TRIGGERED_AND_CAPTURED"

set data [upload_hw_ila_data $ila]
write_hw_ila_data -force -csv_file $csv_file $data
puts "ILA_CSV=$csv_file"
puts "ILA_FRAME0_CAPTURE_COMPLETE"

close_hw_target
disconnect_hw_server
close_hw
exit
