# Read-only: exact pulse-width failing paths + what the 1 GHz clock drives.
set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_routed.dcp}
set outdir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/reports/pl_ddr_mandatory_core_v1/diag_ai_clk}
file mkdir $outdir

open_checkpoint $dcp

puts "=== A. report_timing -check pulse_width (all failing endpoints) ==="
report_timing -check pulse_width -max_paths 20 -file [file join $outdir ai_clk_pw_paths.rpt]

puts "=== B. Sink pins driven by clk_out1_AI_CORE_CLK_ST_1 ==="
set clk [get_clocks clk_out1_AI_CORE_CLK_ST_1]
set nets [get_nets -quiet -of_objects $clk]
puts "  clock net objects: $nets"
foreach n $nets {
    puts "  net $n drivers:"
    foreach d [get_pins -quiet -of_objects [get_nets $n] -filter {DIRECTION == OUT}] { puts "      OUT $d" }
    puts "  net $n sinks (IN pins):"
    set idx 0
    foreach s [get_pins -quiet -of_objects [get_nets $n] -filter {DIRECTION == IN}] {
        puts "      IN  $s  [get_property -quiet REF_PIN_NAME $s] [get_property -quiet LIB_CELL $s]"
        incr idx
        if {$idx > 30} { puts "      ... (truncated)"; break }
    }
}

puts "=== C. cells clocked by clk_out1_AI_CORE_CLK_ST_1 (register clock pins) ==="
set clkpins [get_pins -quiet -filter {IS_CLOCK == 1} -of_objects [get_cells -hierarchical -quiet] -filter "PARENT_CELL =~ *"]
# narrower: find sequential cells whose CLK pin net is this clock
set cells [get_cells -hierarchical -quiet -filter {PRIMITIVE_TYPE =~ REGISTER.* || PRIMITIVE_TYPE =~ .*RAM.* || PRIMITIVE_TYPE =~ .*DSP.*}]
set hits {}
foreach c $cells {
    set cp [get_pins -quiet -of_objects $c -filter {IS_CLOCK == 1}]
    foreach p $cp {
        if {[llength [get_nets -quiet -of_objects $p]] && [get_clocks -quiet -of_objects [get_nets -quiet -of_objects $p]] eq $clk} {
            lappend hits $p
        }
    }
}
puts "  sequential cells on 1 GHz clock: [llength $hits]"
foreach h [lrange $hits 0 40] { puts "      $h" }

puts "DIAG_AI_CLK2_DONE"
close_design
