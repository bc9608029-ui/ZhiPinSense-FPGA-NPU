set project_dir  {F:/Project_vivado/mandatory_core_board_validation_50mhz}
set project_file [file join $project_dir project_1.xpr]
set report_dir   [file join $project_dir reports]

file mkdir $report_dir
open_project $project_file
set_param general.maxThreads 4

set source_set [get_filesets sources_1]
set constr_set [get_filesets constrs_1]

# Replace only copied HDL/data sources inside the new project.  Keep the
# generated Clocking Wizard XCI and its generated targets in sources_1.
set replaceable_sources [concat \
    [get_files -quiet [file join $project_dir src *.sv]] \
    [get_files -quiet [file join $project_dir iq_input.hex]]]
if {[llength $replaceable_sources] > 0} {
    remove_files -fileset $source_set $replaceable_sources
}

set rtl_files [glob -nocomplain [file join $project_dir src *.sv]]
if {[llength $rtl_files] != 9} {
    error "Expected exactly 9 board/core SystemVerilog files, found [llength $rtl_files]"
}
add_files -norecurse -fileset $source_set $rtl_files
add_files -norecurse -fileset $source_set [file join $project_dir iq_input.hex]
foreach f $rtl_files {
    set_property file_type SystemVerilog [get_files $f]
}

set obsolete_clock_xdc [file join $project_dir constraints mandatory_core_50mhz.xdc]
set obsolete_clock_file [get_files -quiet $obsolete_clock_xdc]
if {[llength $obsolete_clock_file] > 0} {
    remove_files -fileset $constr_set $obsolete_clock_file
}

foreach xdc [list \
    [file join $project_dir constraints mandatory_core_reset.xdc]] {
    if {[llength [get_files -quiet $xdc]] == 0} {
        add_files -norecurse -fileset $constr_set $xdc
    }
}

set_property top board_mandatory_core_test_top $source_set
set rom_init_file [file normalize [file join $project_dir iq_input.hex]]
set_property generic [list ROM_INIT_FILE=$rom_init_file] $source_set
puts "ROM_INIT_FILE=$rom_init_file"
update_compile_order -fileset $source_set

cd $project_dir

# Let the project run infrastructure compile the managed Clocking Wizard IP
# and its generated constraints in the supported order.  A direct
# synth_design invocation does not automatically insert managed-IP sources in
# Vivado 2018.3.
generate_target all [get_ips clk_wiz_0]
reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
set synth_status [get_property STATUS [get_runs synth_1]]
puts "SYNTH_RUN_STATUS=$synth_status"
if {![string match "*Complete*" $synth_status]} {
    error "synth_1 did not complete successfully: $synth_status"
}
open_run synth_1

report_utilization -file [file join $report_dir synth_50mhz_utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $report_dir synth_50mhz_utilization_hierarchical.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir synth_50mhz_timing_summary.rpt]
report_drc -file [file join $report_dir synth_50mhz_drc.rpt]
report_clocks -file [file join $report_dir synth_50mhz_clocks.rpt]
report_clock_interaction -file [file join $report_dir synth_50mhz_clock_interaction.rpt]
write_checkpoint -force [file join $report_dir mandatory_core_synth_50mhz.dcp]

set core_clock_candidates {}
foreach candidate [get_clocks -quiet *] {
    set candidate_period [get_property PERIOD $candidate]
    if {$candidate_period ne "" &&
        [expr {abs(double($candidate_period) - 20.0)}] <= 0.001} {
        lappend core_clock_candidates $candidate
    }
}
if {[llength $core_clock_candidates] != 1} {
    puts "AVAILABLE_CLOCKS:"
    foreach candidate [get_clocks -quiet *] {
        puts "  [get_property NAME $candidate] period=[get_property PERIOD $candidate]"
    }
    error "Expected exactly one 20.000 ns generated core clock, found [llength $core_clock_candidates]"
}
set core_clock [lindex $core_clock_candidates 0]
puts "CORE_CLOCK_NAME=[get_property NAME $core_clock]"
puts "CORE_CLOCK_PERIOD_NS=[get_property PERIOD $core_clock]"

# Preserve the full validation datapath until the ILA is added.  These are
# session-only implementation properties and do not modify RTL/XDC/project.
set preserve_cells [get_cells -quiet {core iq_rom replay}]
if {[llength $preserve_cells] != 3} {
    error "Expected core/iq_rom/replay hierarchy was not found"
}
set_property DONT_TOUCH true $preserve_cells
puts "PRESERVED_CELLS=[join $preserve_cells ,]"

opt_design
write_checkpoint -force [file join $report_dir post_opt_50mhz.dcp]
place_design
write_checkpoint -force [file join $report_dir post_place_50mhz.dcp]
phys_opt_design
write_checkpoint -force [file join $report_dir post_physopt_50mhz.dcp]
route_design

report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir routed_50mhz_timing_summary.rpt]
report_timing -delay_type max -max_paths 100 -sort_by group \
    -file [file join $report_dir routed_50mhz_setup_paths.rpt]
report_timing -delay_type min -max_paths 50 -sort_by group \
    -file [file join $report_dir routed_50mhz_hold_paths.rpt]
report_utilization -file [file join $report_dir routed_50mhz_utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $report_dir routed_50mhz_utilization_hierarchical.rpt]
report_route_status -file [file join $report_dir routed_50mhz_route_status.rpt]
report_drc -file [file join $report_dir routed_50mhz_drc.rpt]
report_clocks -file [file join $report_dir routed_50mhz_clocks.rpt]
report_clock_utilization -file [file join $report_dir routed_50mhz_clock_utilization.rpt]
report_clock_interaction -file [file join $report_dir routed_50mhz_clock_interaction.rpt]
if {[catch {
    report_design_analysis -congestion \
        -file [file join $report_dir routed_50mhz_congestion.rpt]
} congestion_error]} {
    puts "CONGESTION_REPORT_WARNING=$congestion_error"
}
write_checkpoint -force [file join $report_dir mandatory_core_routed_50mhz.dcp]

puts "BITSTREAM_GENERATED=NO"
puts "SYNTH_IMPL_50MHZ_COMPLETE"
close_project
