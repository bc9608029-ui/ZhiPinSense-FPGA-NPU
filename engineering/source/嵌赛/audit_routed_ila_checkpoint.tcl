set dcp {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz/mandatory_core_routed_ila_50mhz.dcp}

open_checkpoint $dcp

set setup_path [get_timing_paths -delay_type max -max_paths 1]
set hold_path  [get_timing_paths -delay_type min -max_paths 1]
puts "AUDIT_DESIGN=[current_design]"
puts "AUDIT_PART=[get_property PART [current_design]]"
puts "AUDIT_WNS_NS=[get_property SLACK $setup_path]"
puts "AUDIT_WHS_NS=[get_property SLACK $hold_path]"

set core_clock [get_clocks -quiet clk_out1_clk_wiz_0]
if {[llength $core_clock] != 1} {
    error "Expected one clk_out1_clk_wiz_0 clock, found [llength $core_clock]"
}
puts "AUDIT_CORE_CLOCK_PERIOD_NS=[get_property PERIOD $core_clock]"

set ila [get_debug_cores -quiet u_ila_tensor]
set hub [get_debug_cores -quiet dbg_hub]
if {[llength $ila] != 1 || [llength $hub] != 1} {
    error "Expected one ILA and one debug hub"
}
puts "AUDIT_ILA_DATA_DEPTH=[get_property C_DATA_DEPTH $ila]"
puts "AUDIT_ILA_STORAGE_QUAL=[get_property C_EN_STRG_QUAL $ila]"
puts "AUDIT_ILA_INPUT_PIPE_STAGES=[get_property C_INPUT_PIPE_STAGES $ila]"
puts "AUDIT_ILA_PROBE_PORTS=[llength [get_debug_ports -quiet u_ila_tensor/probe*]]"
puts "AUDIT_ILA_CLOCK_NET=[get_nets -quiet -of_objects [get_debug_ports u_ila_tensor/clk]]"
puts "AUDIT_HUB_CLOCK_NET=[get_nets -quiet -of_objects [get_debug_ports dbg_hub/clk]]"
puts "AUDIT_HUB_CLK_INPUT_FREQ_HZ=[get_property C_CLK_INPUT_FREQ_HZ $hub]"
puts "AUDIT_HUB_CLK_DIVIDER=[get_property C_ENABLE_CLK_DIVIDER $hub]"

set unrouted [get_nets -quiet -filter {ROUTE_STATUS != ROUTED && ROUTE_STATUS != INTRASITE && ROUTE_STATUS != NOLOADS}]
puts "AUDIT_NONROUTED_NET_COUNT=[llength $unrouted]"

check_timing -verbose
report_drc
puts "ROUTED_ILA_CHECKPOINT_AUDIT_COMPLETE"
close_design
