# m1_fmsh_patch_procise.tcl — 在 Procise（FMSH 工具，非 Vivado）下对 M1 两个 raw .bit
# 应用 increment_bit_cfg_v3 -disable_icap，验证 FMSH patch 管线端到端可用。
#
# 关键：set_device / increment_bit_cfg_v3 是 Procise 的 Tcl 命令，不是 Vivado 命令。
# 官方 call_procise_disable_icap.bat 用 procise.exe 加载本类脚本，环境变量由 .bat 注入。

set_device JFMQL30TAI676H

increment_bit_cfg_v3 \
  E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/m1_baseline/npu_raw.bit \
  E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/m1_baseline/npu_disable_icap.bit \
  -disable_icap

increment_bit_cfg_v3 \
  E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/m1_baseline/hdmi_raw.bit \
  E:/FPGA_Work/sdr_full_chain_12class_combined_v1/fpga/m1_baseline/hdmi_disable_icap.bit \
  -disable_icap

puts "M1_FMSH_PATCH_DONE"
exit 0
