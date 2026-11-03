set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
set synth_dcp [file join $project_dir project_1.runs synth_1 board_mandatory_core_test_top.dcp]
set ip_dcp [file join $project_dir ip clk_wiz_0 clk_wiz_0.dcp]

open_checkpoint $synth_dcp
read_checkpoint -cell u_core_clk_wiz $ip_dcp
read_xdc [file join $project_dir project_1.srcs constrs_1 imports vivado_led_setup led_flow_lite.xdc]
read_xdc [file join $project_dir constraints mandatory_core_reset.xdc]

set black_boxes [get_cells -quiet -hierarchical -filter {IS_BLACKBOX == 1}]
puts "BLACK_BOX_COUNT=[llength $black_boxes]"
foreach cell $black_boxes { puts "BLACK_BOX=$cell" }

set clocks [get_clocks -quiet *]
puts "CLOCK_COUNT=[llength $clocks]"
foreach clk $clocks {
  puts "CLOCK=$clk PERIOD=[get_property PERIOD $clk]"
}

puts "STITCHED_RESETFIX_SYNTH_INSPECTION_COMPLETE"
close_design
exit
