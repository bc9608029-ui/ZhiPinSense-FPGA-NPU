# m5_procise_disable_icap_smartscan.tcl — apply FMSH increment_bit_cfg_v3 -disable_icap
# to the smart-scan raw .bit (step 3 of 3).  Procise Tcl (set_device /
# increment_bit_cfg_v3 are Procise commands), loaded by the companion .bat.

set_device JFMQL30TAI676H

increment_bit_cfg_v3 \
  F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/npu_base/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_combined_smartscan.bit \
  F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/outputs/smartscan_candidate_v1/bitstream/smartscan_npu_hdmi_disable_icap.bit.tmp \
  -disable_icap

puts "M5S_FMSH_PATCH_DONE"
exit 0
