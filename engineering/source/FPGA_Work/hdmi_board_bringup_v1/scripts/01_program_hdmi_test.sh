#!/usr/bin/env bash
# 01_program_hdmi_test.sh — TEMPORARY, RECOVERABLE load of the colorbar bitstream.
#
# HARD RULE (SAFETY_GATE G2): first load is a JTAG download to the device only.
# This script NEVER writes QSPI/SD permanent storage.  If it cannot find the
# Procise *_disable_icap.bit it REFUSES to run and tells you to build it first.
# Run on the Windows host only AFTER 00_host_verify passes.
set -u

BITDIR="/f/FPGA_Work/hdmi_board_bringup_v1/fpga/vivado_prj/hdmi_colorbar_720p.runs/impl_1"
BIT="$BITDIR/hdmi_colorbar_720p_top_disable_icap.bit"

# Gate: the Procise-produced bitstream must exist (raw .bit is NOT flashable).
if [ ! -f "$BIT" ]; then
  echo "REFUSE: $BIT not found."
  echo "  Build it first (see fpga/README.md):"
  echo "    1) Vivado: source fpga/build_hdmi_colorbar_720p.tcl"
  echo "    2) Procise: set_device JFMQL30TAI676H"
  echo "       increment_bit_cfg_v3 <raw.bit> <this_file> -disable_icap"
  echo "  This script will NOT proceed, and will NOT flash any permanent storage."
  exit 2
fi

# Gate: confirm the asset is the 悟净 colorbar build, not some other board's bit.
SUMMARY="/f/FPGA_Work/hdmi_board_bringup_v1/fpga/reports/build_summary.txt"
if ! grep -q "TOP=hdmi_colorbar_720p_top" "$SUMMARY" 2>/dev/null; then
  echo "REFUSE: build_summary.txt does not confirm TOP=hdmi_colorbar_720p_top."
  exit 2
fi
if ! grep -q "PART=xc7z030ffg676-2" "$SUMMARY" 2>/dev/null; then
  echo "REFUSE: build_summary.txt does not confirm PART=xc7z030ffg676-2 (FMQL30TAI676H)."
  exit 2
fi

echo "Bitstream checked OK: $BIT"
echo
echo "NEXT (manual, this script does not automate the physical step):"
echo "  1. Connect the PL JTAG (U19) to the host.  Do NOT confuse with PS UART."
echo "  2. Temporary load via Vivado hw_server / xsdb:"
echo "       vivado -mode batch -source scripts/program_jtag_temp.tcl"
echo "     (program_jtag_temp.tcl uses 'program_hw_devices' — a volatile download"
echo "      to the device, never a QSPI/SD write.)"
echo "  3. Watch for heat/smell/abnormal current while powered — if any, cut power."
echo "  4. Then run scripts/02_verify_colorbar.sh."
exit 0
