set project_dir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga}
set integration_dir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/pl_ddr_integration_v1}
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set report_dir [file join $project_dir reports pl_ddr_mandatory_core_v1]
file mkdir $report_dir

open_project $project_file

set integration_sources [concat \
    [glob -nocomplain [file join $integration_dir deps adapters *.sv]] \
    [glob -nocomplain [file join $integration_dir deps frozen *.sv]] \
    [list \
        [file join $integration_dir rtl job_domain_controller.sv] \
        [file join $integration_dir rtl pl_ddr_mandatory_core_regs.sv] \
        [file join $integration_dir rtl pl_ddr_mandatory_core_engine.sv] \
        [file join $integration_dir rtl pl_ddr_mandatory_core_top.sv]]]

foreach source_file $integration_sources {
    if {[llength [get_files -quiet $source_file]] == 0} {
        add_files -fileset sources_1 -norecurse $source_file
    }
    set_property file_type SystemVerilog [get_files $source_file]
}

# Restore the official MIG XCI that the control-only smoke build intentionally
# removed from its project.  The source file itself was never altered.
set mig_xci [file join $project_dir rtl ip mig_7series_0 mig_7series_0.xci]
if {![file exists $mig_xci]} {
    error "Official MIG XCI is missing: $mig_xci"
}
if {[llength [get_files -quiet $mig_xci]] == 0} {
    add_files -fileset sources_1 -norecurse $mig_xci
}

# Vivado 2018.3 Clocking Wizard v6.0, matching the already verified board
# clock recipe: official hp_clk 200 MHz -> MMCM -> BUFG -> core_clk 50 MHz.
if {[llength [get_ips -quiet clk_wiz_core_50]] == 0} {
    file mkdir [file join $project_dir ip]
    create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 \
        -module_name clk_wiz_core_50 -dir [file join $project_dir ip]
    set_property -dict [list \
        CONFIG.PRIMITIVE {MMCM} \
        CONFIG.PRIM_IN_FREQ {200.000} \
        CONFIG.CLKIN1_JITTER_PS {50.0} \
        CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {50.000} \
        CONFIG.CLKOUT1_DRIVES {BUFG} \
        CONFIG.USE_RESET {true} \
        CONFIG.RESET_TYPE {ACTIVE_HIGH} \
        CONFIG.USE_LOCKED {true}] [get_ips clk_wiz_core_50]
    generate_target all [get_ips clk_wiz_core_50]
}

set stage_xdc [file join $integration_dir pl_ddr_mandatory_core_v1.xdc]
if {[llength [get_files -quiet $stage_xdc]] == 0} {
    add_files -fileset constrs_1 -norecurse $stage_xdc
}
set_property is_enabled true [get_files $stage_xdc]
set_property used_in_synthesis true [get_files $stage_xdc]
set_property used_in_implementation true [get_files $stage_xdc]

# The official ai7030.xdc contains SDI hierarchy constraints.  This build has
# no SDR/SDI instance, so retain that source unmodified but disable it.  The
# tailored stage XDC above preserves only the applicable board constraints.
foreach constraint_name {ai7030.xdc impl_constraints.xdc ps_pl_ctrl_smoke_v2.xdc} {
    set constraint_file [get_files -quiet */$constraint_name]
    if {[llength $constraint_file] != 0} {
        set_property is_enabled false $constraint_file
    }
}

set_property top pl_ddr_mandatory_core_top [get_filesets sources_1]
set_property top_auto_set 0 [get_filesets sources_1]
update_compile_order -fileset sources_1

# Preserve the project-local FMSH flow used by the PASS smoke build.
set safe_synth_pre [file join $project_dir fmsh_synthesis_pre_safe.tcl]
if {![file exists $safe_synth_pre]} {
    error "Missing safe FMSH synthesis pre-hook: $safe_synth_pre"
}
set_property STEPS.SYNTH_DESIGN.TCL.PRE $safe_synth_pre [get_runs synth_1]

# Confirm the copied BD address instead of inventing a User_Reg base.
open_bd_design [file join $project_dir fpai_demo_vivado.srcs sources_1 bd ps_ai ps_ai.bd]
set user_seg [get_bd_addr_segs -quiet /processing_system7_0/Data/SEG_User_GP0_Reg]
if {[llength $user_seg] != 1} {
    error "Expected one User_GP0 address segment, found [llength $user_seg]"
}
set address_ch [open [file join $report_dir address_map.txt] w]
puts $address_ch "SEG_User_GP0_Reg OFFSET=[get_property OFFSET $user_seg] RANGE=[get_property RANGE $user_seg]"
puts $address_ch "gp0_manager m3/user custom-op subwindow = OFFSET + 0x00040000"
puts $address_ch "effective register base = 0x400C0000"
close $address_ch
close_bd_design [current_bd_design]

# Run the synthesis gate only in this script.  Implementation is deliberately
# separate so warnings/clocking/CDC can be reviewed before place-and-route.
reset_run synth_1
foreach child_run [get_runs -quiet *_synth_1] {
    if {[get_property NAME $child_run] ne "synth_1"} {
        reset_run $child_run
    }
}
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "synth_1 failed: [get_property STATUS [get_runs synth_1]]"
}

open_run synth_1
report_utilization -hierarchical -file [file join $report_dir post_synth_utilization_hier.rpt]
report_timing_summary -file [file join $report_dir post_synth_timing_summary.rpt]
report_clocks -file [file join $report_dir post_synth_clocks.rpt]
report_clock_interaction -file [file join $report_dir post_synth_clock_interaction.rpt]
report_cdc -details -file [file join $report_dir post_synth_cdc.rpt]
report_methodology -file [file join $report_dir post_synth_methodology.rpt]
check_timing -verbose -file [file join $report_dir post_synth_check_timing.rpt]
report_drc -file [file join $report_dir post_synth_drc.rpt]
close_design

set summary_ch [open [file join $report_dir synthesis_gate.txt] w]
puts $summary_ch "TOP=pl_ddr_mandatory_core_top"
puts $summary_ch "PART=[get_property PART [current_project]]"
puts $summary_ch "SYNTH_STATUS=[get_property STATUS [get_runs synth_1]]"
close $summary_ch
close_project
puts "PL_DDR_MANDATORY_CORE_SYNTHESIS_PASS"
