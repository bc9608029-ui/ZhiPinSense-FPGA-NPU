# m1_quick_check.tcl — M1 快速基线校验（任务 39e5 最终阶段 §四）
#
# 目标：在原已布线 DCP 上执行 DRC / 时序摘要 / 利用率 / bitgen，确认
# Vivado 2018.3 + license + FMSH patch + IP 均可正常加载。所有输出写入
# 合并工程 fpga/m1_baseline/，绝不改写来源工程。
#
# 口径（§四）：快速校验，不跑 synth->place->route 全量重建。

set COMBINED {E:/FPGA_Work/sdr_full_chain_12class_combined_v1}
set OUT [file join $COMBINED fpga m1_baseline]
file mkdir [file join $OUT reports]

set NPU_DCP  {E:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_routed.dcp}
set HDMI_DCP {E:/FPGA_Work/hdmi_framebuffer_ui_v4_fix/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_routed.dcp}

proc m1_one {tag dcp} {
    global OUT
    puts "==${tag}_DCP_OPEN_BEGIN=="
    open_checkpoint $dcp
    puts "==${tag}_DCP_OPEN_OK=="
    puts "==${tag}_PART=[get_property PART [current_design]]=="
    report_drc -file [file join $OUT reports ${tag}_drc.rpt]
    puts "==${tag}_DRC_DONE=="
    report_timing_summary -file [file join $OUT reports ${tag}_timing_summary.rpt]
    puts "==${tag}_TIMING_DONE=="
    report_utilization -file [file join $OUT reports ${tag}_utilization.rpt]
    puts "==${tag}_UTIL_DONE=="
    write_bitstream -force [file join $OUT ${tag}_raw.bit]
    puts "==${tag}_BITGEN_OK=="
    close_design
}

m1_one npu  $NPU_DCP
m1_one hdmi $HDMI_DCP

# FMSH patch（increment_bit_cfg_v3 -disable_icap）：需 project 上下文加载 all_src_files.tcl。
set NPU_PRJ {E:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga}
puts "==PATCH_OPEN_PROJECT_BEGIN=="
open_project [file join $NPU_PRJ fpai_demo_vivado.xpr]
set ::env(JFM_PATH) $NPU_PRJ
source [file join $NPU_PRJ ip_patch run.tcl]
set_device JFMQL30TAI676H
increment_bit_cfg_v3 [file join $OUT npu_raw.bit]  [file join $OUT npu_disable_icap.bit]  -disable_icap
puts "==NPU_PATCH_OK=="
increment_bit_cfg_v3 [file join $OUT hdmi_raw.bit] [file join $OUT hdmi_disable_icap.bit] -disable_icap
puts "==HDMI_PATCH_OK=="
close_project

puts "==M1_ALL_DONE=="
