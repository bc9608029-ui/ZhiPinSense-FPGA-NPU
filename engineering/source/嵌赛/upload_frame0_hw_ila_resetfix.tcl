set ltx_file {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz_resetfix_routed_eco/mandatory_core_routed_ila_50mhz_resetfix.ltx}
set csv_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz/hardware_captures}
set csv_file [file join $csv_dir hardware_capture_frame0_resetfix.csv]
file mkdir $csv_dir

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
if {$ila eq ""} { error "No hardware ILA detected" }
set data [upload_hw_ila_data $ila]
write_hw_ila_data -force -csv_file $csv_file $data
puts "ILA_CSV=$csv_file"
puts "ILA_FRAME0_RESETFIX_UPLOAD_COMPLETE"

close_hw_target
disconnect_hw_server
close_hw
exit
