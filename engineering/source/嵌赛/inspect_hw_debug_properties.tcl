open_hw
connect_hw_server
open_hw_target
set dev [lindex [get_hw_devices] 0]
puts "HW_DEVICE=$dev"
foreach prop {BSCAN_SWITCH_USER_MASK PROGRAM.FILE PROBES.FILE FULL_PROBES.FILE} {
  if {[catch {set value [get_property $prop $dev]} err]} {
    puts "HW_PROP_${prop}_ERROR=$err"
  } else {
    puts "HW_PROP_${prop}=$value"
  }
}
close_hw_target
disconnect_hw_server
close_hw
puts "HW_DEBUG_PROPERTY_INSPECTION_COMPLETE"
exit
