set ltx_file {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz/mandatory_core_routed_ila_50mhz.ltx}

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

set ilas [get_hw_ilas -of_objects $dev]
puts "HW_ILA_COUNT=[llength $ilas]"
foreach ila $ilas {
  puts "HW_ILA=$ila"
  foreach prop {CONTROL.DATA_DEPTH CONTROL.TRIGGER_POSITION CONTROL.CAPTURE_MODE CONTROL.TRIGGER_CONDITION STATUS.CORE_STATUS} {
    if {![catch {set value [get_property $prop $ila]}]} {
      puts "ILA_PROP_${prop}=$value"
    }
  }
  set probes [get_hw_probes -of_objects $ila]
  puts "HW_PROBE_COUNT=[llength $probes]"
  foreach probe $probes {
    set width ""
    catch {set width [get_property WIDTH $probe]}
    puts "HW_PROBE=$probe WIDTH=$width"
  }
}

close_hw_target
disconnect_hw_server
close_hw
puts "HW_ILA_PROBE_ENUMERATION_COMPLETE"
exit
