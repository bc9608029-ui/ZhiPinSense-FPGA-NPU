foreach c {create_project set_device read_verilog read_rtl set_top synthesize syn_project xst_synthesize map opt_design place route read_sdc create_clock report_area report_timing report_clocks report_device_resources save_project} {
 puts "===== HELP $c ====="
 catch {help $c} e
 puts $e
}
exit 0