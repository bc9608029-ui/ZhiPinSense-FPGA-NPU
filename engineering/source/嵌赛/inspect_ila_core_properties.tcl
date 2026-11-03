set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
open_project [file join $project_dir project_1.xpr]
open_run synth_1
create_debug_core u_ila_tensor ila
puts "=== ILA_PROPERTIES_BEGIN ==="
report_property -all [get_debug_cores u_ila_tensor]
puts "=== ILA_PROPERTIES_END ==="
puts "=== CORE_CLOCK_CANDIDATES_BEGIN ==="
foreach pattern [list *core_clk* *clk_out1*] {
    foreach net [get_nets -quiet -hierarchical $pattern] {
        puts [get_property NAME $net]
    }
}
puts "=== CORE_CLOCK_CANDIDATES_END ==="
close_project
