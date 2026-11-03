# m5_procise_disable_icap_combined.tcl — 在 Procise（FMSH 工具，非 Vivado）下对合并 raw .bit
# 应用 increment_bit_cfg_v3 -disable_icap，产出板载可编程位流（临时名 .bit.tmp，全部检查通过后再原子改名）。
#
# 关键：set_device / increment_bit_cfg_v3 是 Procise 的 Tcl 命令，不是 Vivado 命令。
# 由 call_procise_disable_icap_combined.bat 注入环境变量后用 procise.exe 加载本脚本。

set_device JFMQL30TAI676H

increment_bit_cfg_v3 \
  E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/npu_base/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_combined.bit \
  E:/FPGA_Work/sdr_full_chain_12class_combined_v1/outputs/smoke_v1/bitstream/combined_npu_hdmi_disable_icap.bit.tmp \
  -disable_icap

puts "M5_FMSH_PATCH_DONE"
exit 0
