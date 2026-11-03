proc step {name command} {
 puts "TEST_STAGE_BEGIN $name"
 if {[catch {uplevel 1 $command} result]} {puts "TEST_STAGE_FAIL $name $result"; exit 2}
 puts $result
 puts "TEST_STAGE_PASS $name"
}
step project {create_project -name qam_feature_ooc -device JFMQL30TAI676H}
step files {add_design_file -file E:/rml24_fpga_execution_20261027/procise_rtl/qam_feature_pipeline.v}
step top {set_top -top qam_feature_pipeline}
step save {save_project}
step load {load_design -stage_elaborate -no_hier}
step synth {launch_run -stage synthesis}
step clocks {create_clock -name clk -period 10 [get_ports clk]}
step area {report_area}
step edif {write_edif qam_feature_pipeline.edf}
step place {place}
step route {route}
step clock_report {report_clocks}
step timing {report_timing}
step physical {write_phy_design qam_feature_pipeline.phy}
puts "FMQL_OOC_PROJECT_FLOW_PASS"
exit 0