proc step {name command} {
    puts "SMARTSCAN_STAGE_BEGIN $name"
    if {[catch {uplevel 1 $command} result]} {
        puts "SMARTSCAN_STAGE_FAIL $name $result"
        exit 2
    }
    puts $result
    puts "SMARTSCAN_STAGE_PASS $name"
}

# Combined OOC: migrated XFFT 9.1 netlist + window + adapter + u54 writer, in one
# Procise project on JFMQL30TAI676H. The migrated EDIF is staged next to this
# script by scripts/run_combined_ooc.ps1 as smartscan_fft_1024.edif. The migrated
# .fdc is intentionally NOT added: it constrains the standalone core's top-level
# `aclk` port, which does not exist here; the harness top `clk` clock reaches the
# core's aclk through the adapter and is constrained below instead.
set root [file normalize [file dirname [info script]]]
step project {create_project -name smart_scan_combined_ooc -device JFMQL30TAI676H}
step files_fft {add_design_file -file [file join $root smartscan_fft_1024.edif]}
step files_blackbox {add_design_file -file [file join $root smartscan_fft_1024_blackbox.v]}
step files_window {add_design_file -file [file join $root window_mul_q15.v]}
step files_adapter {add_design_file -file [file join $root fft_vendor_ip_adapter.v]}
step files_writer {add_design_file -file [file join $root fft_psd_stream_writer.v]}
step files_harness {add_design_file -file [file join $root smart_scan_combined_ooc_harness.v]}
step top {set_top -top smart_scan_combined_ooc_harness}
step save {save_project}
step load {load_design -stage_elaborate -no_hier}
step synth {launch_run -stage synthesis}
step clock {create_clock -name clk -period 10 [get_ports clk]}
step area {report_area}
step edif {write_edif smart_scan_combined_ooc.edf}
step place {place}
step route {route}
step clocks {report_clocks}
step timing {report_timing}
step physical {write_phy_design smart_scan_combined_ooc.phy}
puts "SMARTSCAN_COMBINED_OOC_RESULT result=PASS device=JFMQL30TAI676H clock_ns=10 includes_fft=YES production_bitstream=NO"
exit 0
