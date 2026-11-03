open_hw
connect_hw_server
open_hw_target
set matches {}
foreach d [get_hw_devices] {
    if {[get_property PART $d] eq "xc7z030"} { lappend matches $d }
}
if {[llength $matches] != 1} { error "Expected exactly one xc7z030" }
set dev [lindex $matches 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
puts "DEVICE=$dev PART=[get_property PART $dev]"
puts "PROGRAM_FILE=[get_property PROGRAM.FILE $dev]"
foreach prop {REGISTER.IR.BIT5_DONE REGISTER.CONFIG_STATUS.BIT13_DONE REGISTER.CONFIG_STATUS.BIT14_INIT_B} {
    if {[lsearch -exact [list_property $dev] $prop] >= 0} {
        puts "$prop=[get_property $prop $dev]"
    }
}
close_hw_target
disconnect_hw_server
close_hw
exit
