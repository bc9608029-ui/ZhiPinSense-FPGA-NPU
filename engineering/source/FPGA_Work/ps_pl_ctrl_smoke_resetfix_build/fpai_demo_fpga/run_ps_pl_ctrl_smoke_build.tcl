set project_dir [file normalize [file dirname [info script]]]
set project_file [file join $project_dir fpai_demo_vivado.xpr]
set report_dir [file join $project_dir reports ps_pl_ctrl_smoke]
file mkdir $report_dir

open_project $project_file

set smoke_sources [list \
    [file join $project_dir rtl ps_pl_ctrl_smoke_regs.sv] \
    [file join $project_dir rtl ps_pl_ctrl_smoke_top.sv]]
foreach source_file $smoke_sources {
    if {[llength [get_files -quiet $source_file]] == 0} {
        add_files -fileset sources_1 -norecurse $source_file
    }
    set_property file_type SystemVerilog [get_files $source_file]
}

# The minimal top has only PS fixed I/O and PS DDR hard pins.  The official
# PL-DDR/SDI/HDMI pin constraints remain unmodified in the copied project but
# are disabled for this control-only build because those ports are absent.
foreach constraint_name {ai7030.xdc impl_constraints.xdc} {
    set constraint_file [get_files -quiet */$constraint_name]
    if {[llength $constraint_file] != 0} {
        set_property is_enabled false $constraint_file
    }
}

# This smoke build intentionally has no PL DDR port or controller.  The copied
# official project still lists its MIG XCI, and the FMSH synthesis pre-hook
# rejects any listed IP without a completed OOC checkpoint even when that IP is
# unreachable from the selected top.  Remove only that unused XCI from this
# copied project; the source file on disk and the official archive stay intact.
set unused_mig [get_files -quiet */mig_7series_0.xci]
if {[llength $unused_mig] != 0} {
    remove_files -fileset sources_1 $unused_mig
}

set_property top ps_pl_ctrl_smoke_top [get_filesets sources_1]
set_property top_auto_set 0 [get_filesets sources_1]
update_compile_order -fileset sources_1

# Keep the Vivado installation read-only.  The wrapper executes the original
# FMSH pre-hook and suppresses only byte-identical device-database copies.
set_property STEPS.SYNTH_DESIGN.TCL.PRE \
    [file join $project_dir safe_synthesis_pre.tcl] [get_runs synth_1]

# The official project already contains the FMSH run-hook properties.  Reuse
# the project-local patch copied from the installed JFM kit.  Do not rerun the
# global installer here: it unnecessarily writes the Vivado installation.
if {![file isdirectory [file join $project_dir ip_patch process_control]]} {
    if {![info exists ::env(JFM_PATH)]} {
        error "JFM_PATH is not set and the project-local ip_patch is absent"
    }
    source [file join $::env(JFM_PATH) ip_patch run.tcl]
    copy_patch
}

# Record the address from this copied BD rather than relying on the example
# application constant.
open_bd_design [file join $project_dir fpai_demo_vivado.srcs sources_1 bd ps_ai ps_ai.bd]
set user_seg [get_bd_addr_segs -quiet /processing_system7_0/Data/SEG_User_GP0_Reg]
if {[llength $user_seg] != 1} {
    error "Expected exactly one User_GP0 address segment, found [llength $user_seg]"
}
set address_ch [open [file join $report_dir address_map.txt] w]
puts $address_ch "SEG_User_GP0_Reg OFFSET=[get_property OFFSET $user_seg] RANGE=[get_property RANGE $user_seg]"
puts $address_ch "gp0_manager m3/user custom-op subwindow = OFFSET + 0x00040000"
puts $address_ch "effective smoke register base = 0x400C0000"
close $address_ch
close_bd_design [current_bd_design]

# Reset every out-of-context child run as well as the parent.  Vivado 2018.3
# can leave child IP runs in ERROR after an interrupted or path-failed launch;
# resetting only synth_1 then refuses to relaunch the dependency graph.
reset_run synth_1
foreach child_run [get_runs -quiet *_synth_1] {
    if {[get_property NAME $child_run] ne "synth_1"} {
        reset_run $child_run
    }
}
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "synth_1 did not complete: [get_property STATUS [get_runs synth_1]]"
}

open_run synth_1
report_utilization -file [file join $report_dir post_synth_utilization.rpt]
report_timing_summary -file [file join $report_dir post_synth_timing_summary.rpt]
report_methodology -file [file join $report_dir post_synth_methodology.rpt]
close_design

reset_run impl_1
launch_runs impl_1 -to_step route_design -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 route did not complete: [get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
report_utilization -file [file join $report_dir routed_utilization.rpt]
report_timing_summary -file [file join $report_dir routed_timing_summary.rpt]
report_route_status -file [file join $report_dir routed_route_status.rpt]
report_drc -file [file join $report_dir routed_drc.rpt]
report_methodology -file [file join $report_dir routed_methodology.rpt]

set worst_path [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
set hold_path [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
set wns [get_property SLACK $worst_path]
set whs [get_property SLACK $hold_path]
set timing_ch [open [file join $report_dir timing_gate.txt] w]
puts $timing_ch "WNS=$wns"
puts $timing_ch "WHS=$whs"
puts $timing_ch "SETUP_PATH=[get_property STARTPOINT_PIN $worst_path] -> [get_property ENDPOINT_PIN $worst_path]"
puts $timing_ch "HOLD_PATH=[get_property STARTPOINT_PIN $hold_path] -> [get_property ENDPOINT_PIN $hold_path]"
close $timing_ch
if {$wns < 0.0 || $whs < 0.0} {
    error "Timing gate failed: WNS=$wns WHS=$whs"
}
close_design

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 bitstream did not complete: [get_property STATUS [get_runs impl_1]]"
}

set summary_ch [open [file join $report_dir build_summary.txt] w]
puts $summary_ch "TOP=ps_pl_ctrl_smoke_top"
puts $summary_ch "PART=[get_property PART [current_project]]"
puts $summary_ch "SYNTH_STATUS=[get_property STATUS [get_runs synth_1]]"
puts $summary_ch "IMPL_STATUS=[get_property STATUS [get_runs impl_1]]"
puts $summary_ch "WNS=$wns"
puts $summary_ch "WHS=$whs"
close $summary_ch

close_project
puts "PS_PL_CTRL_SMOKE_BUILD_PASS"
