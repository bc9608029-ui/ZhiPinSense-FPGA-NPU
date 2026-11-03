open_checkpoint {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz/mandatory_core_routed_ila_50mhz.dcp}

set hubs [get_debug_cores dbg_hub]
puts "DEBUG_HUB_COUNT=[llength $hubs]"
foreach hub $hubs {
  puts "DEBUG_HUB=$hub"
  foreach prop {C_USER_SCAN_CHAIN C_CLK_INPUT_FREQ_HZ C_ENABLE_CLK_DIVIDER C_CLK_INPUT_FREQ_HZ} {
    if {![catch {set value [get_property $prop $hub]}]} {
      puts "DEBUG_HUB_$prop=$value"
    }
  }
}

set ilas [get_debug_cores u_ila_tensor]
puts "DCP_ILA_COUNT=[llength $ilas]"
foreach ila $ilas {
  puts "DCP_ILA=$ila"
}

close_design
puts "DEBUG_HUB_INSPECTION_COMPLETE"
exit
