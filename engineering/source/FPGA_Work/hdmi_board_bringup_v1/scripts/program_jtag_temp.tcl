# program_jtag_temp.tcl — VOLATILE JTAG download of the colorbar bitstream.
#
# This loads the bitstream into the device's configuration memory over JTAG.
# It is a temporary, recoverable load: a power cycle returns the board to its
# previous state.  It does NOT write QSPI or SD permanent storage.
#
# Usage (Vivado Tcl console, with the hw_server connected):
#   source F:/FPGA_Work/hdmi_board_bringup_v1/scripts/program_jtag_temp.tcl

set bit [file normalize "F:/FPGA_Work/hdmi_board_bringup_v1/fpga/vivado_prj/hdmi_colorbar_720p.runs/impl_1/hdmi_colorbar_720p_top_disable_icap.bit"]
if {![file exists $bit]} {
    error "bitstream not found: $bit (build + Procise first)"
}

# Open the hardware manager target (adjust the target index to your cable).
open_hw_manager
connect_hw_server -allow_non_jtag
open_hw_target
current_hw_device [get_hw_devices xc7z030*]
refresh_hw_device -update_hw_probes false [lindex [get_hw_devices] 0]

# Volatile program (no -p, so nothing is persisted to flash).
set_property PROGRAM.FILE $bit [get_hw_devices xc7z030*]
program_hw_devices [get_hw_devices xc7z030*]
puts "JTAG_TEMP_PROGRAM_DONE (volatile; power cycle reverts to previous state)"
