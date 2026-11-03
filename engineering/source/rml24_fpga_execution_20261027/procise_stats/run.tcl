proc step {name command} {
 puts "TEST_STAGE_BEGIN $name"
 if {[catch {uplevel 1 $command} result]} {puts "TEST_STAGE_FAIL $name $result"; exit 2}
 puts $result
 puts "TEST_STAGE_PASS $name"
}
step device {set_device JFMQL30TAI676H}
step input {add_design_file -file E:/rml24_fpga_execution_20261027/source/rtl/frame_statistics.sv}
step load {load_design -stage_elaborate -no_hier}
step top {set_top -top frame_statistics}
step analyze {rtl_analyze}
step clock {create_clock -name clk -period 10 [get_ports clk]}
step synth {synthesize}
step area {report_area}
step edif {write_edif frame_statistics.edf}
step place {place}
step route {route}
step clocks {report_clocks}
step timing {report_timing}
step physical {write_phy_design frame_statistics.phy}
puts "FMQL_OOC_FLOW_PASS"
exit 0