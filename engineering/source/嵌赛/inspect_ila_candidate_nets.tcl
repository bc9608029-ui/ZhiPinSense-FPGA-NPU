set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
open_project [file join $project_dir project_1.xpr]
open_run synth_1

puts "=== MARK_DEBUG_NETS_BEGIN ==="
foreach net [lsort [get_nets -hierarchical -filter {MARK_DEBUG == 1}]] {
    puts [get_property NAME $net]
}
puts "=== MARK_DEBUG_NETS_END ==="

puts "=== CLOCK_NETS_BEGIN ==="
foreach net [get_nets -hierarchical -filter {IS_CLOCK == 1}] {
    puts [get_property NAME $net]
}
puts "=== CLOCK_NETS_END ==="

close_project
