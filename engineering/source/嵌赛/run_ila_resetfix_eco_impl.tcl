set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
set input_dcp [file join $project_dir reports ila_50mhz post_ila_insert_50mhz.dcp]
set report_dir [file join $project_dir reports ila_50mhz_resetfix_eco]
file mkdir $report_dir

set_param general.maxThreads 4
open_checkpoint $input_dcp

# PL_KEY1 remains connected to the test-logic reset synchronizer.  Disconnect
# only the MMCM reset input so core_clk, the Debug Hub and the ILA remain live
# while PL_KEY1 is pressed.
set mmcm_reset_pin [get_pins u_core_clk_wiz/inst/mmcm_adv_inst/RST]
if {[llength $mmcm_reset_pin] != 1} {
    error "Expected one MMCM reset pin"
}
set old_reset_net [get_nets -of_objects $mmcm_reset_pin]
puts "MMCM_RESET_NET_BEFORE=$old_reset_net"
disconnect_net -net $old_reset_net -objects $mmcm_reset_pin
create_cell -reference GND eco_mmcm_reset_gnd
create_net eco_mmcm_reset_const0
connect_net -hier -net eco_mmcm_reset_const0 -objects [list \
    [get_pins eco_mmcm_reset_gnd/G] $mmcm_reset_pin]
set new_reset_net [get_nets -of_objects $mmcm_reset_pin]
puts "MMCM_RESET_NET_AFTER=$new_reset_net"
if {![string match "*eco_mmcm_reset_const0" $new_reset_net]} {
    error "MMCM reset ECO did not connect to constant zero"
}

set debug_hub [get_debug_cores dbg_hub]
if {[llength $debug_hub] != 1} {
    error "Expected exactly one debug hub"
}
set_property C_CLK_INPUT_FREQ_HZ 50000000 $debug_hub
set_property C_ENABLE_CLK_DIVIDER false $debug_hub
puts "DEBUG_HUB_C_CLK_INPUT_FREQ_HZ=[get_property C_CLK_INPUT_FREQ_HZ $debug_hub]"

write_checkpoint -force [file join $report_dir post_eco_preopt_ila_50mhz.dcp]
opt_design
write_checkpoint -force [file join $report_dir post_opt_ila_50mhz.dcp]
place_design
write_checkpoint -force [file join $report_dir post_place_ila_50mhz.dcp]
phys_opt_design
write_checkpoint -force [file join $report_dir post_physopt_ila_50mhz.dcp]
route_design

report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir routed_ila_50mhz_timing_summary.rpt]
report_timing -delay_type max -max_paths 100 -sort_by group \
    -file [file join $report_dir routed_ila_50mhz_setup_paths.rpt]
report_timing -delay_type min -max_paths 50 -sort_by group \
    -file [file join $report_dir routed_ila_50mhz_hold_paths.rpt]
report_utilization -file [file join $report_dir routed_ila_50mhz_utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $report_dir routed_ila_50mhz_utilization_hierarchical.rpt]
report_route_status -file [file join $report_dir routed_ila_50mhz_route_status.rpt]
report_drc -file [file join $report_dir routed_ila_50mhz_drc.rpt]
report_clocks -file [file join $report_dir routed_ila_50mhz_clocks.rpt]
report_clock_utilization -file [file join $report_dir routed_ila_50mhz_clock_utilization.rpt]

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
puts "ILA_RESETFIX_ECO_IMPL_COMPLETE"
close_design
exit
