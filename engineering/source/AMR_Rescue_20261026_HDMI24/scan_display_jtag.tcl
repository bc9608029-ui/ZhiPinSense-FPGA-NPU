open_hw
connect_hw_server
puts "TARGETS=[get_hw_targets]"
foreach t [get_hw_targets] {
 open_hw_target $t
 puts "DEVICES=[get_hw_devices]"
 foreach d [get_hw_devices] {puts "DEVICE=$d PART=[get_property PART $d]"}
 close_hw_target
}
disconnect_hw_server
close_hw
exit