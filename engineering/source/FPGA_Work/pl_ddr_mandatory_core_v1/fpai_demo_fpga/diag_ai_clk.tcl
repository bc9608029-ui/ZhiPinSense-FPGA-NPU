# Read-only trace of clk_out1_AI_CORE_CLK_ST_1 (the 1 GHz AI-core clock).
# No constraint changes, no RTL changes, no bitstream.
set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_routed.dcp}
set outdir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/reports/pl_ddr_mandatory_core_v1/diag_ai_clk}
file mkdir $outdir

open_checkpoint $dcp

set clk [get_clocks clk_out1_AI_CORE_CLK_ST_1]

puts "=== 1. MASTER CLOCK CHAIN of clk_out1_AI_CORE_CLK_ST_1 ==="
set c $clk
for {set i 0} {$i < 8 && [llength $c]} {incr i} {
    set name [get_property NAME $c]
    set period [get_property PERIOD $c]
    set wave [get_property WAVEFORM $c]
    set master [get_property MASTER_CLOCK $c]
    set gen [get_property IS_GENERATED $c]
    puts "  [$i] $name  period=$period  waveform=$wave  generated=$gen"
    if {[llength $master] == 0} { break }
    puts "        master -> [get_property NAME $master]"
    set c $master
}

puts ""
puts "=== 2. PULSE WIDTH / MIN PERIOD detail (report_pulse_width) ==="
report_pulse_width -file [file join $outdir ai_clk_pulse_width.rpt] -verbose

puts ""
puts "=== 3. What clk_out1_AI_CORE_CLK_ST_1 actually drives ==="
report_clock_networks -clock $clk -file [file join $outdir ai_clk_networks.rpt]
set fanout [get_property FANOUT $clk]
puts "  FANOUT(clock)=$fanout"
# List the sink pins driven by the 1 GHz clock
set sinks [get_pins -quiet -of_objects [get_nets -quiet -of_objects $clk] -filter {DIRECTION == IN}]
puts "  Sink pins on 1 GHz clock net (count=[llength $sinks]):"
foreach s [lrange $sinks 0 40] { puts "      $s" }

puts ""
puts "=== 4. Worst setup/hold pulse width paths (report_timing -check pulse_width) ==="
report_timing -delay_type min_max -check pulse_width -max_paths 5 -nworst 1 -file [file join $outdir ai_clk_pw_paths.rpt]

puts "DIAG_AI_CLK_DONE"
close_design
