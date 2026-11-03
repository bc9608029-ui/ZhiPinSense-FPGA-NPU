# Vivado 2018.3 netlist-insertion ILA for the first PS GP0 read transaction.
# This script is sourced after the synthesized netlist is opened and before
# opt_design.  It is diagnostic-only and does not alter the smoke register RTL.

set dbg_nets {}
for {set i 0} {$i < 141} {incr i} {
    set bit_name [format {dbg_gp0_read[%d]} $i]
    set bit_net [get_nets -quiet $bit_name]
    if {[llength $bit_net] != 1} {
        error "Expected exactly one top-level net named $bit_name, found [llength $bit_net]"
    }
    lappend dbg_nets [lindex $bit_net 0]
}

set ila_clk [get_nets -quiet gp_clk]
if {[llength $ila_clk] != 1} {
    error "Expected exactly one top-level gp_clk net for ILA, found [llength $ila_clk]"
}
set ila_clock_obj [get_clocks -quiet -of_objects $ila_clk]
if {[llength $ila_clock_obj] != 1} {
    error "Expected exactly one timing clock on gp_clk, found [llength $ila_clock_obj]"
}
set ila_clock_period [get_property PERIOD $ila_clock_obj]
if {[expr {abs($ila_clock_period - 10.000)}] > 0.001} {
    error "Expected gp_clk to be 100 MHz (10.000 ns), found period $ila_clock_period ns"
}

create_debug_core u_ila_gp0 ila
set_property C_DATA_DEPTH 1024 [get_debug_cores u_ila_gp0]
set_property C_ADV_TRIGGER false [get_debug_cores u_ila_gp0]
set_property C_EN_STRG_QUAL false [get_debug_cores u_ila_gp0]
set_property C_INPUT_PIPE_STAGES 1 [get_debug_cores u_ila_gp0]
set_property port_width 141 [get_debug_ports u_ila_gp0/probe0]
set_property PROBE_TYPE DATA_AND_TRIGGER [get_debug_ports u_ila_gp0/probe0]
connect_debug_port u_ila_gp0/clk $ila_clk
connect_debug_port u_ila_gp0/probe0 $dbg_nets

puts "GP0_ILA_INSERTED PROBE_BITS=[llength $dbg_nets] CLOCK=$ila_clk PERIOD_NS=$ila_clock_period DEPTH=1024"
