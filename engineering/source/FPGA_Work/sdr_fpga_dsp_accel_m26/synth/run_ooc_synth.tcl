# M26 out-of-context synthesis — Vivado batch.  Synthesizes each module alone,
# writes per-module .dcp + utilization/timing/power reports under synth/out/<top>/.
#
#   vivado -mode batch -source run_ooc_synth.tcl
#
# DSP-inference check (spec §五): m26_fir/m26_fft_1024/m26_nco/m26_cfar are each
# synthesized twice — default inference and (* use_dsp = "yes" *) forced — so the
# reports can be diffed.  This script produces REPORTS only; it never generates a
# bitstream (write_bitstream is intentionally absent).

set script_dir [file dirname [file normalize [info script]]]
set rtl_dir    [file normalize [file join $script_dir .. rtl]]
set out_dir    [file join $script_dir out]
file mkdir $out_dir

set tops {
    m26_dc_removal m26_energy_rms m26_signal_presence m26_nco m26_fir
    m26_decimator m26_hann m26_fft_1024 m26_fftshift m26_mag_sq
    m26_noise_floor m26_cfar m26_candidate_merge
    m26_stream_frontend_top m26_spectrum_top
}

# modules whose DSP inference is compared (default vs forced)
set dsp_check { m26_fir m26_fft_1024 m26_nco m26_cfar }

set srcs [glob -nocomplain [file join $rtl_dir *.sv]]
read_verilog -sv {*}$srcs

proc synth_one { top out_dir suffix } {
    set d [file join $out_dir $top]
    file mkdir $d
    synth_design -mode out_of_context -top $top -part xc7z030ffg676-2
    write_checkpoint -force [file join $d $top$suffix.dcp]
    report_utilization -file [file join $d utilization$suffix.rpt]
    report_timing       -file [file join $d timing$suffix.rpt]
    report_power        -file [file join $d power$suffix.rpt]
    puts "  synthesized $top$suffix"
}

foreach top $tops {
    puts "== OOC synth $top =="
    if {[catch { synth_one $top $out_dir {} } err]} {
        puts "ERROR: $top failed: $err"
        exit 1
    }
}

# DSP-inference diff pass (forced use_dsp) for the flagged modules.
foreach top $dsp_check {
    puts "== OOC synth (use_dsp forced) $top =="
    if {[catch { synth_one $top $out_dir _usedsp } err]} {
        puts "ERROR: $top (forced) failed: $err"
        exit 1
    }
}

puts "OOC SYNTH COMPLETE: [llength $tops] modules (+[llength $dsp_check] forced-DSP)"
puts "Reports under $out_dir"
exit 0
