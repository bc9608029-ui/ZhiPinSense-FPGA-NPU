# Read-only: confirm what the 1 GHz clock drives, and what clocks the AI core
# (ZGolo/u_AI_Mate_top) actually uses for its logic.
set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_routed.dcp}
open_checkpoint $dcp

set clk1g [get_clocks clk_out1_AI_CORE_CLK_ST_1]

puts "=== 1. Sink clock pins on clk_out1_AI_CORE_CLK_ST_1 ==="
set nets1g [get_nets -quiet -of_objects $clk1g]
foreach n $nets1g {
    set sinks [get_pins -quiet -of_objects [get_nets $n] -filter {DIRECTION == IN && IS_CLOCK == 1}]
    puts "  clock net $n"
    foreach s $sinks {
        puts "      CLK sink: $s  (cell: [get_property -quiet PARENT_CELL $s])"
    }
    set others [get_pins -quiet -of_objects [get_nets $n] -filter {DIRECTION == IN && IS_CLOCK == 0}]
    puts "    non-clock IN pins: [llength $others]"
}

puts ""
puts "=== 2. Register/FD cells under ZGolo/u_AI_Mate_top, grouped by clock ==="
set ai_cells [get_cells -hierarchical -quiet -filter {NAME =~ *ZGolo/u_AI_Mate_top*}]
puts "  total cells under u_AI_Mate_top: [llength $ai_cells]"
set regs [get_cells -hierarchical -quiet -filter {NAME =~ *ZGolo/u_AI_Mate_top* && (PRIMITIVE_TYPE =~ REGISTER.* || PRIMITIVE_TYPE =~ *FDRE* || PRIMITIVE_TYPE =~ *FDSE* || PRIMITIVE_TYPE =~ *FDPE* || PRIMITIVE_TYPE =~ *FDPE*)}]
puts "  FD/register cells under u_AI_Mate_top: [llength $regs]"

set byclock {}
foreach r $regs {
    set cp [get_pins -quiet -of_objects $r -filter {IS_CLOCK == 1}]
    foreach p $cp {
        set cn [get_clocks -quiet -of_objects [get_nets -quiet -of_objects $p]]
        if {[llength $cn]} {
            set cname [get_property NAME $cn]
            dict incr byclock $cname
        }
    }
}
puts "  FD clock distribution (top 12):"
set sorted [lsort -stride 2 -index 1 -integer -decreasing $byclock]
foreach {c cnt} [lrange $sorted 0 23] { puts "      $cnt  $c" }

puts "DIAG_AI_CLK3_DONE"
close_design
