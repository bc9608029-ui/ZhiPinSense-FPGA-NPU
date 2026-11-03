set dcp {F:/Project_vivado/mandatory_core_board_validation_50mhz/reports/ila_50mhz/mandatory_core_routed_ila_50mhz.dcp}
open_checkpoint $dcp
set p [get_pins u_core_clk_wiz/inst/mmcm_adv_inst/RST]
puts "RST_PIN=$p"
puts "RST_NET=[get_nets -of_objects $p]"
puts "PLACED_CELLS=[llength [get_cells -hier -filter {IS_PLACED == 1}]]"
puts "GND_CELLS=[get_cells -hier -filter {REF_NAME == GND}]"
foreach c [get_cells -hier -filter {REF_NAME == GND}] {
    puts "GND_CELL=$c PIN=[get_pins -of_objects $c] NET=[get_nets -of_objects [get_pins -of_objects $c]]"
}
exit
