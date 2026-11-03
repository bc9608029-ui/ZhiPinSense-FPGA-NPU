set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
set project_file [file join $project_dir project_1.xpr]
set report_dir [file join $project_dir reports ila_50mhz_resetfix]
file mkdir $report_dir

proc require_net {net_name} {
    set result [get_nets -quiet $net_name]
    if {[llength $result] != 1} {
        error "Expected exactly one net named $net_name, found [llength $result]"
    }
    return $result
}

proc get_or_create_probe_port {core probe_index} {
    if {$probe_index == 0} {
        set port [get_debug_ports ${core}/probe0]
        if {[llength $port] != 1} {
            error "Expected the default ${core}/probe0 debug port"
        }
        return $port
    }
    return [create_debug_port $core probe]
}

proc add_scalar_probe {core probe_index net_name map_channel} {
    set port [get_or_create_probe_port $core $probe_index]
    set_property port_width 1 $port
    set net [require_net $net_name]
    connect_debug_port $port $net
    puts $map_channel [format {probe%d[0] <= %s} $probe_index $net_name]
}

proc add_bus_probe {core probe_index base_name width map_channel} {
    set port [get_or_create_probe_port $core $probe_index]
    set_property port_width $width $port
    set nets {}
    for {set bit 0} {$bit < $width} {incr bit} {
        set net_name [format {%s[%d]} $base_name $bit]
        lappend nets [require_net $net_name]
        puts $map_channel [format {probe%d[%d] <= %s} $probe_index $bit $net_name]
    }
    connect_debug_port $port $nets
}

set_param general.maxThreads 4
set synth_dcp [file join $project_dir project_1.runs synth_1 board_mandatory_core_test_top.dcp]
if {![file exists $synth_dcp]} {
    error "Synthesis checkpoint does not exist: $synth_dcp"
}
set ip_dcp [file join $project_dir ip clk_wiz_0 clk_wiz_0.dcp]
open_checkpoint $synth_dcp
read_checkpoint -cell u_core_clk_wiz $ip_dcp
read_xdc [file join $project_dir project_1.srcs constrs_1 imports vivado_led_setup led_flow_lite.xdc]
read_xdc [file join $project_dir constraints mandatory_core_reset.xdc]

set black_boxes [get_cells -quiet -hierarchical -filter {IS_BLACKBOX == 1}]
if {[llength $black_boxes] != 0} {
    error "Implementation design still contains black boxes: $black_boxes"
}

set preserve_cells [get_cells -quiet {core iq_rom replay}]
if {[llength $preserve_cells] != 3} {
    error "Expected core/iq_rom/replay hierarchy was not found"
}
set_property DONT_TOUCH true $preserve_cells

set ila_core [create_debug_core u_ila_tensor ila]
set_property C_DATA_DEPTH 2048 $ila_core
set_property C_ADV_TRIGGER false $ila_core
set_property C_EN_STRG_QUAL true $ila_core
set_property C_INPUT_PIPE_STAGES 0 $ila_core
set_property C_TRIGIN_EN false $ila_core
set_property C_TRIGOUT_EN false $ila_core
set_property ALL_PROBE_SAME_MU true $ila_core
set_property ALL_PROBE_SAME_MU_CNT 4 $ila_core

set ila_clock [require_net core_clk]
connect_debug_port [get_debug_ports u_ila_tensor/clk] $ila_clock

set map_channel [open [file join $report_dir ila_probe_map.txt] w]
puts $map_channel "ILA clock <= core_clk (50 MHz)"
puts $map_channel "C_DATA_DEPTH=2048"
puts $map_channel "C_EN_STRG_QUAL=true"

set probe_index 0
# m_write_ready is tied high in this board-validation top, so an accepted
# tensor write is exactly m_write_valid.  Vivado collapses the separate
# dbg_tensor_transfer alias onto the same net; probing both aliases leaves one
# debug channel unconnected during implement_debug_core.  Keep the real
# interface signals and use m_write_valid as the storage qualifier.
add_scalar_probe $ila_core $probe_index m_write_valid $map_channel; incr probe_index
add_scalar_probe $ila_core $probe_index m_write_ready $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_iq_i_data 8 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_iq_q_data 8 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_power_data 8 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_lag_re_data 8 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_lag_im_data 8 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_iq_i_addr 11 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_iq_q_addr 11 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_power_addr 12 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_lag_re_addr 12 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_lag_im_addr 12 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_sample_index 10 $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index m_frame_id 32 $map_channel; incr probe_index
add_scalar_probe $ila_core $probe_index m_buffer_id $map_channel; incr probe_index
add_scalar_probe $ila_core $probe_index m_frame_start $map_channel; incr probe_index
add_scalar_probe $ila_core $probe_index m_frame_done $map_channel; incr probe_index
add_scalar_probe $ila_core $probe_index m_frame_error $map_channel; incr probe_index
add_scalar_probe $ila_core $probe_index m_irq $map_channel; incr probe_index
add_bus_probe    $ila_core $probe_index buffer_busy 2 $map_channel; incr probe_index
add_scalar_probe $ila_core $probe_index dbg_sticky_error $map_channel; incr probe_index
close $map_channel

if {$probe_index != 21} {
    error "Expected 21 ILA probes, created $probe_index"
}

write_checkpoint -force [file join $report_dir pre_ila_implement_50mhz.dcp]
implement_debug_core
set debug_hub [get_debug_cores dbg_hub]
if {[llength $debug_hub] != 1} {
    error "Expected exactly one debug hub after ILA insertion"
}
set_property C_CLK_INPUT_FREQ_HZ 50000000 $debug_hub
set_property C_ENABLE_CLK_DIVIDER false $debug_hub
puts "DEBUG_HUB_C_CLK_INPUT_FREQ_HZ=[get_property C_CLK_INPUT_FREQ_HZ $debug_hub]"
puts "DEBUG_HUB_C_ENABLE_CLK_DIVIDER=[get_property C_ENABLE_CLK_DIVIDER $debug_hub]"
write_checkpoint -force [file join $report_dir post_ila_insert_50mhz.dcp]
write_debug_probes -force [file join $report_dir mandatory_core_ila_50mhz.ltx]
report_utilization -file [file join $report_dir post_ila_synth_utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $report_dir post_ila_synth_utilization_hierarchical.rpt]

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
report_clock_interaction -file [file join $report_dir routed_ila_50mhz_clock_interaction.rpt]
if {[catch {
    report_design_analysis -congestion \
        -file [file join $report_dir routed_ila_50mhz_congestion.rpt]
} congestion_error]} {
    puts "CONGESTION_REPORT_WARNING=$congestion_error"
}
write_checkpoint -force [file join $report_dir mandatory_core_routed_ila_50mhz.dcp]
write_debug_probes -force [file join $report_dir mandatory_core_routed_ila_50mhz.ltx]

puts "ILA_PROBE_COUNT=$probe_index"
puts "ILA_DATA_WIDTH=151"
puts "ILA_DATA_DEPTH=2048"
puts "BITSTREAM_GENERATED=NO"
puts "ILA_SYNTH_IMPL_50MHZ_COMPLETE"
close_design
