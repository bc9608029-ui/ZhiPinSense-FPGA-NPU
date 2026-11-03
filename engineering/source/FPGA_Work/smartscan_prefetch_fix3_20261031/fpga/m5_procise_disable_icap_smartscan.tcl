# m5_procise_disable_icap_smartscan.tcl — apply FMSH increment_bit_cfg_v3 -disable_icap
# to the smart-scan raw .bit (step 3 of 3).  Procise Tcl (set_device /
# increment_bit_cfg_v3 are Procise commands), loaded by the companion .bat.

set_device JFMQL30TAI676H

increment_bit_cfg_v3 \
  E:/FPGA_Work/smartscan_prefetch_fix3_20261031/fpga/npu_base/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_combined_smartscan.bit \
  E:/FPGA_Work/smartscan_prefetch_fix3_20261031/outputs/smartscan_candidate_v1/bitstream/smartscan_npu_hdmi_disable_icap.bit.tmp \
  -disable_icap

puts "M5S_FMSH_PATCH_DONE"
exit 0
