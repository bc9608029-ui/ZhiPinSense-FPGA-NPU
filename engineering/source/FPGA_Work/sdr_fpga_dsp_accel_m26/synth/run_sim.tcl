# M26 behavioral simulation — Vivado xsim batch flow.  Compiles rtl/*.sv + sim/*.sv
# and runs each self-checking testbench.  Testbenches call $fatal on mismatch, so a
# non-zero xsim return marks a failure.
#
#   vivado -mode batch -source run_sim.tcl
#
# Requires the Vivado simulator (xvlog/xelab/xsim) on PATH.

set script_dir [file dirname [file normalize [info script]]]
set rtl_dir    [file normalize [file join $script_dir .. rtl]]
set sim_dir    [file normalize [file join $script_dir .. sim]]

set tbs {
    m26_tb_stream_frontend
    m26_tb_spectrum
    m26_tb_cfar
    m26_tb_median
    m26_tb_fir
}

set rtl_srcs [glob -nocomplain [file join $rtl_dir *.sv]]

foreach tb $tbs {
    set tb_file [file join $sim_dir $tb.sv]
    if {![file exists $tb_file]} { puts "ERROR: missing $tb_file"; exit 1 }

    puts "== compile $tb =="
    if {[catch { exec xvlog -sv {*}$rtl_srcs $tb_file } err]} {
        puts "xvlog error: $err"; exit 1
    }
    if {[catch { exec xelab $tb -s snap_$tb -debug typical } err]} {
        puts "xelab error: $err"; exit 1
    }
    puts "== run $tb =="
    if {[catch { exec xsim snap_$tb -runall } err]} {
        puts "xsim FAILED: $tb"; puts $err; exit 1
    }
}

puts "SIM OK: [llength $tbs] testbenches passed"
exit 0
