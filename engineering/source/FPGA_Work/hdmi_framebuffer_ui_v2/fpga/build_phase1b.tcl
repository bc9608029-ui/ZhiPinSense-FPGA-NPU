# build_phase1b.tcl — Phase 1B PL build: PS DDR framebuffer (DOUBLE buffer) -> 720p HDMI.
#
# Same as Phase 1A but with the double-buffer read path: fb_read_720p now selects
# between read_addr_0 (buffer 0) and read_addr_1 (= buffer 0 + one frame) via a
# 2-bit select driven by frame_ctrl.camera_wr_addr[1:0] (register 0x40080050).
# The 720p HDMI timing / TMDS pins / clock chain are UNCHANGED from Phase 1A.
#
# Reuses the official ps_ai.bd (PS7 + PS DDR3 + HP/GP ports) VERBATIM — no DDR
# parameters are hand-entered (directive #1).  Adds the FMSH PS_AI IP repo
# (processing_system7:5.5) and the read path RTL.
#
# Vivado 2018.3 ONLY (D:/Xilinx2018.3/Vivado/2018.3).  2020.2 is HW-Manager-only.
#
# Usage (Vivado 2018.3 batch):
#   vivado -mode batch -source build_phase1b.tcl
# On success it prints PHASE1B_PL_BUILD_PASS and writes reports/build_summary.txt.
# A SEPARATE Procise step then produces the flashable *_disable_icap.bit (never
# run here — that is a board-bring-up step, not a PL build step).

set script_dir  [file normalize [file dirname [info script]]]
set project_dir [file join $script_dir vivado_prj]

# Start from a clean project directory every run.  A stale project-local
# ip_patch/ from a prior run makes the FMSH copy_patch take a re-entrant path
# that closes the stdout channel in batch mode ("can not find channel named
# stdout" inside show_ip_patch_version).  Removing it forces a fresh copy.
if {[file exists $project_dir]} {
    file delete -force $project_dir
}

set rtl_dir     [file join $script_dir rtl]
set display_dir [file join $rtl_dir display]
set ip_dir      [file join $rtl_dir ip]
set bd_dir      [file join $script_dir bd ps_ai]
set ip_repo     [file join $script_dir ip_repo PS_AI_IP]
set constr_dir  [file join $script_dir constrs]
set report_dir  [file join $script_dir reports]
file mkdir $report_dir

# ---- FMSH JFM kit (patch + device database) --------------------------------
if {![info exists ::env(JFM_PATH)]} {
    set ::env(JFM_PATH) "D:/FMSH/JFM_Kits"
}
set jfm_path $::env(JFM_PATH)
if {![file exists [file join $jfm_path ip_patch run.tcl]]} {
    error "JFM_PATH=$jfm_path does not contain ip_patch/run.tcl — set JFM_PATH to the FMSH JFM_Kits directory"
}

# ---- FMSH PS_AI IP repo (processing_system7:5.5) ---------------------------
if {![file exists [file join $ip_repo processing_system7_v5_5 component.xml]]} {
    error "FMSH PS_AI IP repo not found at $ip_repo — expected processing_system7_v5_5/component.xml"
}

# ---- project ---------------------------------------------------------------
set part "xc7z030ffg676-2"   ;# FMQL30TAI <-> xc7z030ffg676-2 (official mapping)
create_project hdmi_framebuffer_720p $project_dir -part $part -force

# Resolve the FMSH processing_system7:5.5 IP before importing the block design.
set_property ip_repo_paths [list $ip_repo] [current_project]
update_ip_catalog

# ---- block design (ps_ai: PS7 + PS DDR3 + HP/GP + AI control) --------------
# add the .bd, NOT the auto-generated hdl/ps_ai_wrapper.v (we use the hand-written
# rtl/ps_ai_wrapper.sv, which instantiates the BD's own `ps_ai` module).
set bd_file [file join $bd_dir ps_ai.bd]
add_files -norecurse $bd_file
set_property used_in_synthesis 1 [get_files $bd_file]
generate_target all [get_files $bd_file]

# ---- RTL (hand-written + reused official display/read modules) -------------
add_files -norecurse [list \
    [file join $rtl_dir ps_ai_wrapper.sv] \
    [file join $rtl_dir hdmi_framebuffer_720p_top.sv] \
    [file join $rtl_dir fb_read_720p.sv] \
    [file join $rtl_dir axi3_to_axilite_bridge.sv] \
    [file join $display_dir frame_ctrl.v] \
    [file join $display_dir frame_read_write_largebuf.v] \
    [file join $display_dir frame_fifo_read.v] \
    [file join $display_dir frame_fifo_write.v] \
    [file join $display_dir aq_axi_master.v] \
    [file join $display_dir video_rect_read_data.v] \
    [file join $display_dir level_cross.v] \
    [file join $display_dir pulse_cross_camera.v] \
    [file join $display_dir bridge_s.v] \
    [file join $display_dir color_bar.v] \
    [file join $display_dir uihdmitx.v] \
    [file join $display_dir TMDSEncoder.vhd] \
    [file join $display_dir oserdese2_10to1.v] \
    [file join $display_dir timing_gen_xy.v] \
    [file join $display_dir video_define.v] \
]

# ---- IP XCIs instantiated by the reused modules ----------------------------
#   clk_wiz_0                 -> ps_ai_wrapper (gp_axi_aclk 100M + clk_200mhz 200M)
#   afifo_16i_64o_largebuf    -> frame_read_write_largebuf (write_buf)
#   fifo_1                    -> frame_read_write_largebuf (fifo_1_u0)
#   afifo_64i_16o_128         -> frame_read_write_largebuf (read_buf)
add_files -norecurse [list \
    [file join $ip_dir clk_wiz_0 clk_wiz_0.xci] \
    [file join $ip_dir afifo_16i_64o_largebuf afifo_16i_64o_largebuf.xci] \
    [file join $ip_dir fifo_1 fifo_1.xci] \
    [file join $ip_dir afifo_64i_16o_128 afifo_64i_16o_128.xci] \
]

# Mixed-language project: pin the VHDL + SystemVerilog files explicitly.
set_property file_type VHDL          [get_files [file join $display_dir TMDSEncoder.vhd]]
set_property file_type SystemVerilog [get_files [file join $rtl_dir ps_ai_wrapper.sv]]
set_property file_type SystemVerilog [get_files [file join $rtl_dir hdmi_framebuffer_720p_top.sv]]
set_property file_type SystemVerilog [get_files [file join $rtl_dir fb_read_720p.sv]]
set_property file_type SystemVerilog [get_files [file join $rtl_dir axi3_to_axilite_bridge.sv]]

add_files -fileset constrs_1 -norecurse [file join $constr_dir hdmi_framebuffer_720p.xdc]

set_property top hdmi_framebuffer_720p_top [get_filesets sources_1]
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

# ---- implementation (route) ------------------------------------------------
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
# CDC verification: proves ASYNC_REG + pin-based clock groups are in effect and
# the async boundaries still hold (see docs/CDC_WAIVERS.md).
report_cdc -details -file [file join $report_dir routed_report_cdc.rpt]
report_clock_interaction -file [file join $report_dir routed_clock_interaction.rpt]
report_clocks -file [file join $report_dir routed_clocks.rpt]

# Timing gate: the 371.25 MHz TMDS clock and 74.25 MHz pixel clock must both
# meet setup and hold.
set worst_path [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
set hold_path  [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
set wns [get_property SLACK $worst_path]
set whs [get_property SLACK $hold_path]

# DRC gate: count ERROR-severity violations in the report.  The report prints
# violations as lines starting with "ERROR:" / "WARNING:" at column 0, so the
# summary table (title-case "Error"/"Warning") is not double-counted.
set drc_fh [open [file join $report_dir routed_drc.rpt] r]
set drc_txt [read $drc_fh]
close $drc_fh
set drc_err_cnt  [llength [regexp -all -inline -line {^ERROR:}   $drc_txt]]
set drc_warn_cnt [llength [regexp -all -inline -line {^WARNING:} $drc_txt]]

set timing_ch [open [file join $report_dir timing_gate.txt] w]
puts $timing_ch "WNS=$wns"
puts $timing_ch "WHS=$whs"
puts $timing_ch "DRC_ERRORS=$drc_err_cnt"
puts $timing_ch "DRC_WARNINGS=$drc_warn_cnt"
puts $timing_ch "SETUP_PATH=[get_property STARTPOINT_PIN $worst_path] -> [get_property ENDPOINT_PIN $worst_path]"
puts $timing_ch "HOLD_PATH=[get_property STARTPOINT_PIN $hold_path] -> [get_property ENDPOINT_PIN $hold_path]"
close $timing_ch
if {$wns < 0.0 || $whs < 0.0} {
    error "Timing gate failed: WNS=$wns WHS=$whs"
}
if {$drc_err_cnt > 0} {
    error "DRC gate failed: $drc_err_cnt ERROR-severity violations (see routed_drc.rpt)"
}
close_design

# ---- bitstream -------------------------------------------------------------
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "impl_1 bitstream did not complete: [get_property STATUS [get_runs impl_1]]"
}

set bit_file [file normalize [file join [get_property DIRECTORY [get_runs impl_1]] hdmi_framebuffer_720p_top.bit]]
set summary_ch [open [file join $report_dir build_summary.txt] w]
puts $summary_ch "TOP=hdmi_framebuffer_720p_top"
puts $summary_ch "PART=[get_property PART [current_project]]"
puts $summary_ch "SYNTH_STATUS=[get_property STATUS [get_runs synth_1]]"
puts $summary_ch "IMPL_STATUS=[get_property STATUS [get_runs impl_1]]"
puts $summary_ch "WNS=$wns"
puts $summary_ch "WHS=$whs"
puts $summary_ch "DRC_ERRORS=$drc_err_cnt"
puts $summary_ch "DRC_WARNINGS=$drc_warn_cnt"
puts $summary_ch "BITSTREAM=$bit_file"
close $summary_ch

close_project
puts "PHASE1B_PL_BUILD_PASS"
puts "Bitstream: $bit_file"
puts "Next (separate Procise step, board bring-up only): produce *_disable_icap.bit"
