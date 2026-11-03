# procise_run_disable_icap.tcl — Phase 1A: post-process the PL bitstream for
# temporary JTAG loading (disable the ICAP reconfig loop so the bitstream can be
# loaded over JTAG into an already-running board without hanging).
#
# Run via Procise (NOT Vivado), from cmd:
#   call_procise_disable_icap.bat
# or directly:
#   D:/fudanwei/Procise/bin/procise.exe F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/procise_run_disable_icap.tcl
#
# Input  : the Vivado 2018.3 bitstream (hdmi_framebuffer_720p_top.bit)
# Output : *_disable_icap.bit — load THIS one over JTAG, never the raw .bit.
#
# Mirrors ps_pl_ctrl_smoke_resetfix/procise_run_disable_icap.tcl (proven).

set_device JFMQL30TAI676H
increment_bit_cfg_v3  F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top.bit F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top_disable_icap.bit -disable_icap
