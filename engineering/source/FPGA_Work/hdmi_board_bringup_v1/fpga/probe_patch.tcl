# probe_patch.tcl — verify the FMSH patch applies to a fresh project in this
# Vivado install (no synthesis).  Prints PROBE_* lines and exits.
set script_dir [file normalize [file dirname [info script]]]
set project_dir [file join $script_dir vivado_prj]
set rtl_dir     [file join $script_dir rtl]
set constr_dir  [file join $script_dir constrs]
set ::env(JFM_PATH) "D:/FMSH/JFM_Kits"

create_project hdmi_colorbar_720p $project_dir -part xc7z030ffg676-2 -force
add_files -norecurse [list \
    [file join $rtl_dir color_bar.v] \
    [file join $rtl_dir uihdmitx.v] \
    [file join $rtl_dir TMDSEncoder.vhd] \
    [file join $rtl_dir oserdese2_10to1.v] \
    [file join $rtl_dir video_define.v] \
    [file join $rtl_dir hdmi_colorbar_720p_top.v]]
set_property file_type VHDL [get_files [file join $rtl_dir TMDSEncoder.vhd]]
add_files -fileset constrs_1 -norecurse [file join $constr_dir hdmi_colorbar_720p.xdc]
set_property top hdmi_colorbar_720p_top [get_filesets sources_1]
update_compile_order -fileset sources_1

puts "PROBE: project DIRECTORY = [get_property DIRECTORY [current_project]]"
puts "PROBE: PART = [get_property PART [current_project]]"
source [file join $::env(JFM_PATH) ip_patch run.tcl]
puts "PROBE: add_hook_tcl_to_prj defined = [expr {[info procs add_hook_tcl_to_prj] ne {}}]"
puts "PROBE: post_write_bitstream_patch defined = [expr {[info procs post_write_bitstream_patch] ne {}}]"
puts "PROBE: ip_patch copied to project = [expr {[file isdirectory [file join $project_dir ip_patch process_control]]}]"
if {[info procs add_hook_tcl_to_prj] ne {}} {
    add_hook_tcl_to_prj
    puts "PROBE: add_hook_tcl_to_prj returned OK"
}
puts "PROBE: synth_1 PRE hook = [get_property STEPS.SYNTH_DESIGN.TCL.PRE [get_runs synth_1]]"
puts "PROBE: impl_1 bitstream POST hook = [get_property STEPS.WRITE_BITSTREAM.TCL.POST [get_runs impl_1]]"
close_project
puts "PROBE_DONE"
