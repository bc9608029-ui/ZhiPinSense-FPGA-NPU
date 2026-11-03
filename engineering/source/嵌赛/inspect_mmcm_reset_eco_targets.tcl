set dcp {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz/post_ila_insert_50mhz.dcp}
open_checkpoint $dcp

puts "MMCM_CELLS:"
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ *MMCME2*}] {
  puts "CELL=$cell REF=[get_property REF_NAME $cell]"
  foreach pin [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == RST}] {
    puts "  RESET_PIN=$pin NET=[get_nets -quiet -of_objects $pin]"
  }
}

puts "RESET_RELATED_PINS:"
foreach pin [get_pins -quiet -hierarchical -filter {NAME =~ *reset* || NAME =~ *RST*}] {
  puts "PIN=$pin REF_PIN=[get_property REF_PIN_NAME $pin] NET=[get_nets -quiet -of_objects $pin]"
}

puts "GND_CELLS=[get_cells -quiet -hierarchical -filter {REF_NAME == GND}]"
puts "MMCM_RESET_ECO_INSPECTION_COMPLETE"
close_design
exit
