proc step {name command} {
    puts "SMARTSCAN_STAGE_BEGIN $name"
    if {[catch {uplevel 1 $command} result]} {
        puts "SMARTSCAN_STAGE_FAIL $name $result"
        exit 2
    }
    puts $result
    puts "SMARTSCAN_STAGE_PASS $name"
}

# Production datapath OOC: migrated XFFT 9.1 netlist + Hann framer + adapter +
# u54 writer + double-buffer + status, all in one Procise project on
# JFMQL30TAI676H. The migrated EDIF is staged next to this script by
# scripts/run_production_ooc.ps1 as smartscan_fft_1024.edif. The core's own .fdc
# is intentionally omitted (see run_combined_ooc.tcl); the harness `clk` clock
# reaches the core's aclk through the adapter and is constrained below.
set root [file normalize [file dirname [info script]]]
step project {create_project -name smart_scan_production_ooc -device JFMQL30TAI676H}
step files_fft {add_design_file -file [file join $root smartscan_fft_1024.edif]}
step files_blackbox {add_design_file -file [file join $root smartscan_fft_1024_blackbox.v]}
step files_window {add_design_file -file [file join $root window_mul_q15.v]}
step files_adapter {add_design_file -file [file join $root fft_vendor_ip_adapter.v]}
step files_writer {add_design_file -file [file join $root fft_psd_stream_writer.v]}
step files_rom {add_design_file -file [file join $root hann_coeff_rom.v]}
step files_framer {add_design_file -file [file join $root smart_scan_framer.v]}
step files_buffers {add_design_file -file [file join $root smart_scan_psd_buffers.v]}
step files_top {add_design_file -file [file join $root smart_scan_top.v]}
step files_harness {add_design_file -file [file join $root smart_scan_production_ooc_harness.v]}
step top {set_top -top smart_scan_production_ooc_harness}
step save {save_project}
step load {load_design -stage_elaborate -no_hier}
step synth {launch_run -stage synthesis}
step clock {create_clock -name clk -period 10 [get_ports clk]}
step area {report_area}
step edif {write_edif smart_scan_production_ooc.edf}
step place {place}
step route {route}
step clocks {report_clocks}
step timing {report_timing}
step physical {write_phy_design smart_scan_production_ooc.phy}
puts "SMARTSCAN_PRODUCTION_OOC_RESULT result=PASS device=JFMQL30TAI676H clock_ns=10 includes_fft=YES includes_hann=YES includes_double_buffer=YES production_bitstream=NO"
exit 0
