set expected_part "xc7z030"

open_hw
connect_hw_server

set targets [get_hw_targets]
puts "JTAG_TARGET_COUNT=[llength $targets]"
foreach target $targets {
    puts "JTAG_TARGET=$target"
}

if {[llength $targets] != 1} {
    puts "JTAG_PROBE_STOP: expected exactly one hardware target"
    disconnect_hw_server
    close_hw
    exit 2
}

current_hw_target [lindex $targets 0]
open_hw_target

set devices [get_hw_devices]
puts "JTAG_DEVICE_COUNT=[llength $devices]"
foreach device $devices {
    puts "JTAG_DEVICE=$device PART=[get_property PART $device]"
}

set matching_devices [get_hw_devices -filter "PART == $expected_part"]
puts "JTAG_EXPECTED_DEVICE_COUNT=[llength $matching_devices]"

if {[llength $matching_devices] != 1} {
    puts "JTAG_PROBE_STOP: expected exactly one $expected_part device"
    close_hw_target
    disconnect_hw_server
    close_hw
    exit 3
}

puts "JTAG_PROBE_PASS DEVICE=[lindex $matching_devices 0] PART=$expected_part"

close_hw_target
disconnect_hw_server
close_hw
exit 0
