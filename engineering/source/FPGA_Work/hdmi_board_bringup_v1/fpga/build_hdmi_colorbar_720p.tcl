# build_hdmi_colorbar_720p.tcl
# Minimal 720p HDMI colorbar build for the FMQL30TAI (悟净) board.
#
# NOT RUN in this round (this is a pending-vivado-build package).  Running it
# requires Vivado (this machine has 2020.2 at D:/Xilinx/Vivado/2020.2) with the
# FMSH JFM kit patch, and produces hdmi_colorbar_720p_top.bit.  A separate
# Procise step then produces the flashable *_disable_icap.bit.
#
# The official FMSH flow is documented for Vivado 2018.3; the identical
# synth/impl/DRC/timing-gate structure below is lifted from the user's proven
# run_ps_pl_ctrl_smoke_build.tcl, which built successfully on this machine.
#
# Usage (Vivado Tcl console, or `vivado -mode batch -source this_file`):
#   source build_hdmi_colorbar_720p.tcl
# On success it prints HDMI_COLORBAR_720P_BUILD_PASS and writes
# reports/build_summary.txt.

set script_dir [file normalize [file dirname [info script]]]
set project_dir [file join $script_dir vivado_prj]

# Start from a clean project directory every run.  A stale project-local
# ip_patch/ from a prior run makes the FMSH copy_patch take a re-entrant path
# that closes the stdout channel in batch mode (observed: "can not find channel
# named stdout" inside show_ip_patch_version).  Removing it forces copy_patch
# to do a fresh copy — the path proven to work (see probe_patch.tcl).
if {[file exists $project_dir]} {
    file delete -force $project_dir
}

set rtl_dir     [file join $script_dir rtl]
set constr_dir  [file join $script_dir constrs]
set report_dir  [file join $script_dir reports]
file mkdir $report_dir

# ---- FMSH JFM kit (patch + device database) -------------------------------
if {![info exists ::env(JFM_PATH)]} {
    set ::env(JFM_PATH) "D:/FMSH/JFM_Kits"
}
set jfm_path $::env(JFM_PATH)
if {![file exists [file join $jfm_path ip_patch run.tcl]]} {
    error "JFM_PATH=$jfm_path does not contain ip_patch/run.tcl — set JFM_PATH to the FMSH JFM_Kits directory"
}

# ---- project ---------------------------------------------------------------
set part "xc7z030ffg676-2"   ;# FMQL30TAI <-> xc7z030ffg676-2 (official mapping)
create_project hdmi_colorbar_720p $project_dir -part $part -force

add_files -norecurse [list \
    [file join $rtl_dir color_bar.v] \
    [file join $rtl_dir uihdmitx.v] \
    [file join $rtl_dir TMDSEncoder.vhd] \
    [file join $rtl_dir oserdese2_10to1.v] \
    [file join $rtl_dir video_define.v] \
    [file join $rtl_dir hdmi_colorbar_720p_top.v] \
]
# Mixed-language project: pin the VHDL file explicitly.
set_property file_type VHDL    [get_files [file join $rtl_dir TMDSEncoder.vhd]]
set_property file_type Verilog [get_files [file join $rtl_dir color_bar.v]]
set_property file_type Verilog [get_files [file join $rtl_dir uihdmitx.v]]
set_property file_type Verilog [get_files [file join $rtl_dir oserdese2_10to1.v]]

add_files -fileset constrs_1 -norecurse [file join $constr_dir hdmi_colorbar_720p.xdc]

set_property top hdmi_colorbar_720p_top [get_filesets sources_1]
set_property top_auto_set 0 [get_filesets sources_1]
update_compile_order -fileset sources_1

# ---- FMSH patch (official two commands) ------------------------------------
source [file join $jfm_path ip_patch run.tcl]
add_hook_tcl_to_prj

# ---- synthesis -------------------------------------------------------------
reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "synth_1 did not complete: [get_property STATUS [get_runs synth_1]]"
}
open_run synth_1
report_utilization -file [file join $report_dir post_synth_utilization.rpt]
report_timing_summary -file [file join $report_dir post_synth_timing_summary.rpt]
close_design

# ---- implementation (route) -------------------------------------------------
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

# Timing gate: the 371.25 MHz TMDS clock and 74.25 MHz pixel clock must both
# meet setup and hold.  (If WNS is negative on the 371.25 MHz BUFG path, the
# fix is to route the 5x clock through a BUFIO in the HDMI IO bank — the demo
# uses a clk_wiz for this.  Not attempted here; see README.)
set worst_path [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
set hold_path  [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
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

# ---- bitstream -------------------------------------------------------------
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 bitstream did not complete: [get_property STATUS [get_runs impl_1]]"
}

set bit_file [file normalize [file join [get_property DIRECTORY [get_runs impl_1]] hdmi_colorbar_720p_top.bit]]
set summary_ch [open [file join $report_dir build_summary.txt] w]
puts $summary_ch "TOP=hdmi_colorbar_720p_top"
puts $summary_ch "PART=[get_property PART [current_project]]"
puts $summary_ch "SYNTH_STATUS=[get_property STATUS [get_runs synth_1]]"
puts $summary_ch "IMPL_STATUS=[get_property STATUS [get_runs impl_1]]"
puts $summary_ch "WNS=$wns"
puts $summary_ch "WHS=$whs"
puts $summary_ch "BITSTREAM=$bit_file"
close $summary_ch

close_project
puts "HDMI_COLORBAR_720P_BUILD_PASS"
puts "Next: run Procise to produce the flashable *_disable_icap.bit (see README)."
