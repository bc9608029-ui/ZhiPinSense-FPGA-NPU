set ltx_file {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz_resetfix_routed_eco/mandatory_core_routed_ila_50mhz_resetfix.ltx}
set csv_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz/hardware_captures}
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
set frame_start_probe [get_hw_probes -of_objects $ila -filter {NAME =~ "*m_frame_start"}]
set frame_id_probe [get_hw_probes -of_objects $ila -filter {NAME =~ "*m_frame_id*"}]
set write_valid_probe [get_hw_probes -of_objects $ila -filter {NAME =~ "*m_write_valid"}]
if {[llength $frame_start_probe] != 1 || [llength $frame_id_probe] != 1 || [llength $write_valid_probe] != 1} {
    error "Could not uniquely resolve frame_start/frame_id/write_valid probes"
}

set_property CONTROL.DATA_DEPTH 2048 $ila
set_property CONTROL.TRIGGER_POSITION 0 $ila
set_property CONTROL.TRIGGER_CONDITION AND $ila
set_property CONTROL.CAPTURE_MODE BASIC $ila
set_property CONTROL.CAPTURE_CONDITION AND $ila
set_property CAPTURE_COMPARE_VALUE {eq1'b1} $write_valid_probe

foreach start_frame {1 3 5 7 9 11 13 15 17} {
    set end_frame [expr {$start_frame + 1}]
    set_property TRIGGER_COMPARE_VALUE {eq1'b1} $frame_start_probe
    set_property TRIGGER_COMPARE_VALUE [format "eq32'h%08x" $start_frame] $frame_id_probe
    run_hw_ila $ila
    puts [format "ILA_ARMED_FRAMES_%02d_%02d_PRESS_AND_RELEASE_PL_KEY1" $start_frame $end_frame]
    flush stdout
    wait_on_hw_ila $ila
    puts [format "ILA_CAPTURED_FRAMES_%02d_%02d" $start_frame $end_frame]
    set data [upload_hw_ila_data $ila]
    set csv_file [file join $csv_dir [format "hardware_capture_frames_%02d_%02d_resetfix.csv" $start_frame $end_frame]]
    write_hw_ila_data -force -csv_file $csv_file $data
    puts "ILA_CSV=$csv_file"
    flush stdout
}

puts "ILA_REMAINING_FRAME_PAIRS_CAPTURE_COMPLETE"
close_hw_target
disconnect_hw_server
close_hw
exit
