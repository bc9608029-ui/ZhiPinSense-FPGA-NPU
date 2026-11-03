set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
set input_dcp [file join $project_dir reports ila_50mhz mandatory_core_routed_ila_50mhz.dcp]
set report_dir [file join $project_dir reports ila_50mhz_resetfix_routed_eco]
file mkdir $report_dir

set_param general.maxThreads 4
open_checkpoint $input_dcp

# Keep the already placed/routed ILA implementation.  PL_KEY1 continues to
# reset the test logic, but the MMCM reset is tied low so the ILA clock remains
# alive while the pushbutton is held.
set mmcm_reset_pin [get_pins u_core_clk_wiz/inst/mmcm_adv_inst/RST]
set old_reset_net [get_nets -of_objects $mmcm_reset_pin]
set const0_net [get_nets {u_core_clk_wiz/inst/<const0>}]
if {[llength $mmcm_reset_pin] != 1 || [llength $const0_net] != 1} {
    error "Could not resolve MMCM reset ECO objects"
}
puts "MMCM_RESET_NET_BEFORE=$old_reset_net"
disconnect_net -net $old_reset_net -objects $mmcm_reset_pin
connect_net -hier -net $const0_net -objects $mmcm_reset_pin
set new_reset_net [get_nets -of_objects $mmcm_reset_pin]
puts "MMCM_RESET_NET_AFTER=$new_reset_net"
if {$new_reset_net ne $const0_net} {
    error "MMCM reset ECO did not connect to existing constant-zero net"
}

# Re-run routing incrementally after the one-pin ECO, then verify timing/DRC.
route_design
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir routed_ila_50mhz_timing_summary.rpt]
report_utilization -file [file join $report_dir routed_ila_50mhz_utilization.rpt]
report_route_status -file [file join $report_dir routed_ila_50mhz_route_status.rpt]
report_drc -file [file join $report_dir routed_ila_50mhz_drc.rpt]
report_clocks -file [file join $report_dir routed_ila_50mhz_clocks.rpt]

set worst_setup [get_timing_paths -delay_type max -max_paths 1]
set worst_hold [get_timing_paths -delay_type min -max_paths 1]
set wns [get_property SLACK $worst_setup]
set whs [get_property SLACK $worst_hold]
puts "ROUTED_WNS=$wns"
puts "ROUTED_WHS=$whs"
if {$wns < 0.0} { error "Setup timing failed: WNS=$wns" }
if {$whs < 0.0} { error "Hold timing failed: WHS=$whs" }

write_checkpoint -force [file join $report_dir mandatory_core_routed_ila_50mhz_resetfix.dcp]
write_debug_probes -force [file join $report_dir mandatory_core_routed_ila_50mhz_resetfix.ltx]
puts "ROUTED_ILA_RESETFIX_ECO_COMPLETE"
exit
