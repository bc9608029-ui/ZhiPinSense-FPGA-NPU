proc step {name command} {
    puts "SMARTSCAN_STAGE_BEGIN $name"
    if {[catch {uplevel 1 $command} result]} {
        puts "SMARTSCAN_STAGE_FAIL $name $result"
        exit 2
    }
    puts $result
    puts "SMARTSCAN_STAGE_PASS $name"
}

set root [file normalize [file dirname [info script]]]
step project {create_project -name smart_scan_postfft_ooc -device JFMQL30TAI676H}
step files_window {add_design_file -file [file join $root window_mul_q15.v]}
step files_writer {add_design_file -file [file join $root fft_psd_stream_writer.v]}
step files_harness {add_design_file -file [file join $root smart_scan_postfft_ooc_harness.v]}
step top {set_top -top smart_scan_postfft_ooc_harness}
step save {save_project}
step load {load_design -stage_elaborate -no_hier}
step synth {launch_run -stage synthesis}
step clock {create_clock -name clk -period 10 [get_ports clk]}
step area {report_area}
step edif {write_edif smart_scan_postfft_ooc.edf}
step place {place}
step route {route}
step clocks {report_clocks}
step timing {report_timing}
step physical {write_phy_design smart_scan_postfft_ooc.phy}
puts "SMARTSCAN_PROCISE_OOC_RESULT result=PASS device=JFMQL30TAI676H clock_ns=10 production_bitstream=NO"
exit 0
