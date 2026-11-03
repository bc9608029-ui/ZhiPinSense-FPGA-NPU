# write_bitstream_manual.tcl — 单进程手动跑 write_bitstream（绕开 launch_runs 并发，
# 规避 360 U盘保镖对 exFAT F 盘的随机 "Access is denied" 拦截）。
#
# 前提：impl_1 的 route_design 已手动完成（routed.dcp 已生成）。
# 用法（Vivado 2018.3 batch）：
#   vivado -mode batch -source write_bitstream_manual.tcl
# 成功输出 MANUAL_WRITE_BITSTREAM_DONE 与 hdmi_framebuffer_720p_top.bit。
# FMSH 补丁 write_bitstream_post 钩子会自动产出 *_disable_icap.bit。

set script_dir  [file normalize [file dirname [info script]]]
set project_dir [file join $script_dir vivado_prj]
set xpr_file    [file join $project_dir hdmi_framebuffer_720p.xpr]
set runs_dir    [file join $project_dir hdmi_framebuffer_720p.runs]
set bit_file    [file join $runs_dir impl_1 hdmi_framebuffer_720p_top.bit]

if {![file exists $xpr_file]} {
    error "project not found: $xpr_file"
}
if {![file exists [file join $runs_dir impl_1 hdmi_framebuffer_720p_top_routed.dcp]]} {
    error "routed.dcp not found — run route_design first"
}

open_project $xpr_file

# 重新挂 FMSH 补丁（新会话需重注册 write_bitstream_post 钩子）。
if {![info exists ::env(JFM_PATH)]} {
    set ::env(JFM_PATH) "D:/FMSH/JFM_Kits"
}
set jfm_path $::env(JFM_PATH)
if {![file exists [file join $jfm_path ip_patch run.tcl]]} {
    error "JFM_PATH=$jfm_path does not contain ip_patch/run.tcl"
}
source [file join $jfm_path ip_patch run.tcl]
add_hook_tcl_to_prj

open_run impl_1
write_bitstream -force $bit_file

puts "MANUAL_WRITE_BITSTREAM_DONE"
puts "Bitstream: $bit_file"
if {[file exists [file join $runs_dir impl_1 hdmi_framebuffer_720p_top_disable_icap.bit]]} {
    puts "DISABLE_ICAP_AUTO_GENERATED"
} else {
    puts "DISABLE_ICAP_NOT_AUTO (use procise_run_disable_icap.tcl as fallback)"
}
close_project
