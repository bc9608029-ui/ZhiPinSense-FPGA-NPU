# M26 RTL lint — Vivado batch. Reads every rtl/*.sv, elaborates each top-level
# module (RTL elaboration only, no mapping), and prints the error/warning count.
#
#   vivado -mode batch -source run_lint.tcl
#
# Non-zero check: any [synth_design -rtl] returning "ERROR" is reported and the
# script exits 1.  This is a lint gate, not a synthesis gate.

set script_dir [file dirname [file normalize [info script]]]
set rtl_dir    [file normalize [file join $script_dir .. rtl]]

set tops {
    m26_dc_removal m26_energy_rms m26_signal_presence m26_nco m26_fir
    m26_decimator m26_hann m26_fft_1024 m26_fftshift m26_mag_sq
    m26_noise_floor m26_cfar m26_candidate_merge
    m26_stream_frontend_top m26_spectrum_top
}

set srcs [glob -nocomplain [file join $rtl_dir *.sv]]
if {[llength $srcs] == 0} { puts "ERROR: no .sv in $rtl_dir"; exit 1 }

read_verilog -sv {*}$srcs

set failed 0
foreach top $tops {
    puts "== lint $top =="
    if {[catch {
        synth_design -mode out_of_context -top $top -part xc7z030ffg676-2 -rtl
    } err]} {
        puts "ERROR: lint failed for $top: $err"
        incr failed
    }
}

if {$failed != 0} {
    puts "LINT FAILED: $failed module(s)"
    exit 1
}
puts "LINT OK: [llength $tops] modules elaborated"
exit 0
