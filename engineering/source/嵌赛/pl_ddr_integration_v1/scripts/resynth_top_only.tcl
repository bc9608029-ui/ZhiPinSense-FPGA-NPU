set project_dir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga}
set integration_dir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/pl_ddr_integration_v1}
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set report_dir [file join $project_dir reports pl_ddr_mandatory_core_v1]
file mkdir $report_dir

open_project $project_file

# Refresh the copied integration sources without touching the official project
# or any frozen Mandatory Core source.
foreach source_file [list \
    [file join $integration_dir rtl job_domain_controller.sv] \
    [file join $integration_dir rtl pl_ddr_mandatory_core_regs.sv] \
    [file join $integration_dir rtl pl_ddr_mandatory_core_engine.sv] \
    [file join $integration_dir rtl pl_ddr_mandatory_core_top.sv]] {
    if {[llength [get_files -quiet $source_file]] == 0} {
        add_files -fileset sources_1 -norecurse $source_file
    }
    set_property file_type SystemVerilog [get_files $source_file]
}

# The vendor project XML carries two obsolete utility-file records.  They are
# not assigned as implementation hooks and the files are absent in the copied
# official tree.  Remove only these dangling records from this independent
# integration project so project-open diagnostics remain meaningful.
foreach missing_name {implementation_place_pre.tcl implementation_place_post.tcl} {
    set missing_obj [get_files -quiet */$missing_name]
    if {[llength $missing_obj] != 0} {
        remove_files $missing_obj
    }
}

set_property top pl_ddr_mandatory_core_top [get_filesets sources_1]
set_property top_auto_set 0 [get_filesets sources_1]
update_compile_order -fileset sources_1

set safe_synth_pre [file join $project_dir fmsh_synthesis_pre_safe.tcl]
set_property STEPS.SYNTH_DESIGN.TCL.PRE $safe_synth_pre [get_runs synth_1]

# Keep completed OOC IP products; only the changed top-level netlist is rebuilt.
reset_run synth_1
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "synth_1 failed: [get_property STATUS [get_runs synth_1]]"
}

open_run synth_1
report_utilization -hierarchical -file [file join $report_dir post_synth_utilization_hier.rpt] -force
report_timing_summary -file [file join $report_dir post_synth_timing_summary.rpt] -force
report_clocks -file [file join $report_dir post_synth_clocks.rpt] -force
report_clock_interaction -file [file join $report_dir post_synth_clock_interaction.rpt] -force
report_cdc -details -file [file join $report_dir post_synth_cdc.rpt] -force
report_methodology -file [file join $report_dir post_synth_methodology.rpt] -force
check_timing -verbose -file [file join $report_dir post_synth_check_timing.rpt] -force
report_drc -file [file join $report_dir post_synth_drc.rpt] -force
if {[llength [get_bus_skews -quiet]] != 0} {
    report_bus_skew -file [file join $report_dir post_synth_bus_skew.rpt] -force
}
close_design
close_project
puts "PL_DDR_MANDATORY_CORE_RESYNTH_PASS"
