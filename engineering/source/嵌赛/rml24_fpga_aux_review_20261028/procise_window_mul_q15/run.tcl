proc step {name command} {
 puts "TEST_STAGE_BEGIN $name"
 if {[catch {uplevel 1 $command} result]} {puts "TEST_STAGE_FAIL $name $result"; exit 2}
 puts $result
 puts "TEST_STAGE_PASS $name"
}
step project {create_project -name window_mul_q15_ooc -device JFMQL30TAI676H}
step files {add_design_file -file E:/rml24_fpga_aux_execution_20261028/procise_window_mul_q15/window_mul_q15.v}
step top {set_top -top window_mul_q15}
step save {save_project}
step load {load_design -stage_elaborate -no_hier}
step synth {launch_run -stage synthesis}
step clocks {create_clock -name clk -period 10 [get_ports clk]}
step area {report_area}
step edif {write_edif window_mul_q15.edf}
step place {place}
step route {route}
step clock_report {report_clocks}
step timing {report_timing}
step physical {write_phy_design window_mul_q15.phy}
puts "FMQL_OOC_PROJECT_FLOW_PASS"
exit 0