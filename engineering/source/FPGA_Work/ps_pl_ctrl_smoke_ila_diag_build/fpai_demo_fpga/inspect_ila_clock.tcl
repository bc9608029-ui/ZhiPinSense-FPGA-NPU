set project_dir [file normalize [file dirname [info script]]]
open_project [file join $project_dir fpai_demo_vivado.xpr]
open_run synth_1

puts "=== CLOCKS ==="
foreach obj [get_clocks -quiet] {
    puts "CLOCK=$obj PERIOD=[get_property PERIOD $obj] SOURCE_PINS=[get_property SOURCE_PINS $obj]"
}

puts "=== SMOKE CELLS ==="
foreach obj [get_cells -hier -quiet -filter {NAME =~ *smoke*}] {
    puts "CELL=$obj REF=[get_property REF_NAME $obj]"
}

puts "=== SMOKE PINS ==="
foreach obj [get_pins -hier -quiet -filter {NAME =~ *smoke*}] {
    puts "PIN=$obj REF_PIN=[get_property REF_PIN_NAME $obj] DIR=[get_property DIRECTION $obj]"
}

puts "=== CLOCK-LIKE TOP NETS ==="
foreach obj [get_nets -quiet -filter {NAME =~ *clk*}] {
    puts "NET=$obj CLOCKS=[get_clocks -quiet -of_objects $obj]"
}

close_design
close_project
