set project_file {F:/Project_vivado/mandatory_core_board_validation/project_1.xpr}
set report_dir  {F:/Project_vivado/mandatory_core_board_validation/reports/impl_200mhz_preserved_baseline}

file mkdir $report_dir
open_project $project_file

set_param general.maxThreads 4

if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "synth_1 is not complete"
}

# Run implementation in this Vivado process.  This avoids a Windows child-run
# launcher permission failure while preserving the normal default implementation
# sequence.  Deliberately do not call write_bitstream.
open_run synth_1

# MARK_DEBUG nets alone are not sufficient to preserve their full combinational
# fan-in cone when no ILA is instantiated yet.  Apply session-only hierarchy
# preservation so this baseline routes the actual ROM and Mandatory Core.  This
# property is not written back to RTL, XDC, or the project.
set preserve_cells [get_cells -quiet {core iq_rom replay}]
if {[llength $preserve_cells] != 3} {
    error "Expected core/iq_rom/replay hierarchy was not found"
}
set_property DONT_TOUCH true $preserve_cells
puts "PRESERVED_CELLS=[join $preserve_cells ,]"

opt_design
write_checkpoint -force [file join $report_dir post_opt_200mhz.dcp]
place_design
write_checkpoint -force [file join $report_dir post_place_200mhz.dcp]
phys_opt_design
write_checkpoint -force [file join $report_dir post_physopt_200mhz.dcp]
route_design

report_timing_summary -delay_type min_max -max_paths 50 -report_unconstrained \
    -file [file join $report_dir routed_timing_summary.rpt]
report_timing -delay_type max -max_paths 100 -sort_by group \
    -file [file join $report_dir routed_setup_paths.rpt]
report_timing -delay_type min -max_paths 50 -sort_by group \
    -file [file join $report_dir routed_hold_paths.rpt]
report_utilization -file [file join $report_dir routed_utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $report_dir routed_utilization_hierarchical.rpt]
report_route_status -file [file join $report_dir routed_route_status.rpt]
report_drc -file [file join $report_dir routed_drc.rpt]
report_clock_utilization -file [file join $report_dir routed_clock_utilization.rpt]

# Congestion reporting is diagnostic only; keep the implementation intact.
if {[catch {
    report_design_analysis -congestion \
        -file [file join $report_dir routed_congestion.rpt]
} congestion_error]} {
    puts "CONGESTION_REPORT_WARNING=$congestion_error"
}

write_checkpoint -force [file join $report_dir mandatory_core_routed_200mhz.dcp]

puts "BITSTREAM_GENERATED=NO"
puts "IMPL_200MHZ_BASELINE_PASS"
close_project
