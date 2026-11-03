open_project {F:/Project_vivado/mandatory_core_board_validation/project_1.xpr}
open_run synth_1

puts "MARK_DEBUG_NETS_BEGIN"
foreach n [get_nets -hierarchical -filter {MARK_DEBUG == 1}] {
    puts "MARK_DEBUG [get_property NAME $n] DONT_TOUCH=[get_property DONT_TOUCH $n]"
}
puts "MARK_DEBUG_NETS_END"

puts "HIER_CELLS_BEGIN"
foreach c [get_cells -hierarchical -filter {NAME =~ core || NAME =~ iq_rom || NAME =~ replay}] {
    puts "CELL [get_property NAME $c] REF=[get_property REF_NAME $c] DONT_TOUCH=[get_property DONT_TOUCH $c]"
}
puts "HIER_CELLS_END"

close_project
