set project_root [file normalize [file dirname [info script]]]
set xpr_path [file join $project_root project_1.xpr]
set report_dir [file normalize [file join $project_root reports]]
set vector_path [file normalize [file join $project_root iq_input.hex]]
file mkdir $report_dir

open_project $xpr_path
set source_set [get_filesets sources_1]

if {[get_property PART [current_project]] ne "xc7z030ffg676-2"} {
    error "Unexpected part: [get_property PART [current_project]]"
}
if {[get_property top $source_set] ne "board_mandatory_core_test_top"} {
    error "Unexpected synthesis top: [get_property top $source_set]"
}

update_compile_order -fileset $source_set
reset_run synth_1
# Vivado 2018.3 resolves $readmemh relative to the run directory during an
# out-of-context run.  Keep the project-managed immutable copy there as well.
file mkdir [file join $project_root project_1.runs synth_1]
file copy -force $vector_path [file join $project_root project_1.runs synth_1 iq_input.hex]
launch_runs synth_1 -jobs 8
wait_on_run synth_1

set run_status [get_property STATUS [get_runs synth_1]]
puts "SYNTH_RUN_STATUS=$run_status"
if {![string match "*Complete*" $run_status]} {
    error "Synthesis did not complete: $run_status"
}

open_run synth_1

report_utilization -file [file join $report_dir post_synth_utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $report_dir post_synth_utilization_hierarchical.rpt]
report_timing_summary -delay_type max_min -max_paths 20 -report_unconstrained \
    -file [file join $report_dir post_synth_timing_summary.rpt]
report_drc -file [file join $report_dir post_synth_drc.rpt]
report_clock_utilization -file [file join $report_dir post_synth_clock_utilization.rpt]
catch {report_ram_utilization -file [file join $report_dir post_synth_ram_utilization.rpt]} ram_result

set inventory [open [file join $report_dir post_synth_primitive_inventory.rpt] w]
foreach ref_pattern {LUT1 LUT2 LUT3 LUT4 LUT5 LUT6 FDRE FDSE FDCE RAM32* RAM64* RAM128* RAM256* RAM512* RAMB18* RAMB36* DSP48* BUFG* IBUFDS} {
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
puts "FIRST_SYNTHESIS_PASS"
