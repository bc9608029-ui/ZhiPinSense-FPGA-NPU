# write_bitstream_launch.tcl — 通过 run 管理器重跑 write_bitstream（单进程 jobs=1），
# 让 FMSH 的 STEPS.WRITE_BITSTREAM.TCL.POST 钩子（write_bitstream_post.tcl →
# post_write_bitstream_patch）真正触发，给 .bit 打上 FMSH IP patch。
#
# 背景：之前用 write_bitstream_manual.tcl 直接 write_bitstream -force，绕过了 run 管理器，
# POST 钩子没跑，procise 检测到 "IP Patch version: 0XFFFFFFFF"（v2 正常是 53180205）。
# 本脚本只跑 write_bitstream 这一步（route 已完成），不重跑 opt/place/route。
#
# 用法：vivado -mode batch -source write_bitstream_launch.tcl

set script_dir  [file normalize [file dirname [info script]]]
set project_dir [file join $script_dir vivado_prj]
set xpr_file    [file join $project_dir hdmi_framebuffer_720p.xpr]
set runs_dir    [file join $project_dir hdmi_framebuffer_720p.runs]
set bit_file    [file join $runs_dir impl_1 hdmi_framebuffer_720p_top.bit]

if {![file exists $xpr_file]} { error "project not found: $xpr_file" }

open_project $xpr_file

puts "=== pre-check: run status / hook ==="
puts "STATUS=[get_property STATUS [get_runs impl_1]]"
puts "PROGRESS=[get_property PROGRESS [get_runs impl_1]]"
puts "WB_POST=[get_property STEPS.WRITE_BITSTREAM.TCL.POST [get_runs impl_1]]"

# 只推进下一步（write_bitstream），route 已完成，不会重跑。
launch_runs impl_1 -next_step -jobs 1
wait_on_run impl_1

puts "=== post-check ==="
puts "STATUS=[get_property STATUS [get_runs impl_1]]"
puts "PROGRESS=[get_property PROGRESS [get_runs impl_1]]"
puts "Bitstream exists=[file exists $bit_file] size=[file size $bit_file]"

close_project
puts "LAUNCH_WRITE_BITSTREAM_DONE"
