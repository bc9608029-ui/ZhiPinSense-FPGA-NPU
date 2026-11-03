set project_root [file normalize [file dirname [info script]]]
set xpr_path [file join $project_root project_1.xpr]
set report_dir [file normalize [file join $project_root reports]]
file mkdir $report_dir

open_project $xpr_path
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {
    error "synth_1 is not complete: [get_property STATUS [get_runs synth_1]]"
}
open_run synth_1

report_utilization -file [file join $report_dir post_synth_utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $report_dir post_synth_utilization_hierarchical.rpt]
report_timing_summary -delay_type min_max -max_paths 20 -report_unconstrained \
    -file [file join $report_dir post_synth_timing_summary.rpt]
report_drc -file [file join $report_dir post_synth_drc.rpt]
report_clock_utilization -file [file join $report_dir post_synth_clock_utilization.rpt]
catch {report_ram_utilization -file [file join $report_dir post_synth_ram_utilization.rpt]} ram_result

set inventory [open [file join $report_dir post_synth_primitive_inventory.rpt] w]
foreach ref_pattern {LUT1 LUT2 LUT3 LUT4 LUT5 LUT6 FDRE FDSE FDCE FDPE RAM32* RAM64* RAM128* RAM256* RAM512* RAMB18* RAMB36* DSP48* BUFG* IBUFDS} {
    set cells [get_cells -hierarchical -quiet -filter "REF_NAME =~ $ref_pattern"]
    puts $inventory "$ref_pattern [llength $cells]"
}
close $inventory

set focused [open [file join $report_dir post_synth_focused_cells.rpt] w]
foreach pattern {*iq_rom* *input_fifo* *quant_i* *quant_q* *quant_power* *quant_lag_re* *quant_lag_im* *packer* *replay*} {
    puts $focused "===== $pattern ====="
    foreach cell [lsort [get_cells -hierarchical -quiet -filter "NAME =~ $pattern"]] {
        puts $focused "$cell [get_property REF_NAME $cell]"
    }
}
close $focused

write_checkpoint -force [file join $report_dir mandatory_core_post_synth.dcp]
close_project
puts "SYNTH_REPORTS_PASS"
