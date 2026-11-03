#!/usr/bin/env bash
# 00_host_verify.sh — HOST-side pre-flight.  No board, no build, no flash.
#
# Verifies the host toolchain and package assets exist and are the expected
# versions.  Prints PASS/FAIL per item; exits nonzero if any FAIL.
# Run on the Windows host (Git Bash):  bash scripts/00_host_verify.sh
set -u

fail=0
check() { # check <label> <path...>
  local label="$1"; shift
  for p in "$@"; do
    if [ -e "$p" ]; then echo "PASS  $label : $p"; return 0; fi
  done
  echo "FAIL  $label : not found (looked at: $*)"; fail=1
}

echo "== Vivado =="
check "vivado 2020.2" "/d/Xilinx/Vivado/2020.2/settings64.bat"

echo "== FMSH JFM kit =="
check "JFM_KITS ip_patch" "/d/FMSH/JFM_Kits/ip_patch/run.tcl"

echo "== Procise =="
check "Procise" "/f/嵌赛/05_Procise"

echo "== package display RTL (official copies) =="
check "color_bar.v"        "/f/FPGA_Work/hdmi_board_bringup_v1/fpga/rtl/color_bar.v"
check "uihdmitx.v"         "/f/FPGA_Work/hdmi_board_bringup_v1/fpga/rtl/uihdmitx.v"
check "TMDSEncoder.vhd"    "/f/FPGA_Work/hdmi_board_bringup_v1/fpga/rtl/TMDSEncoder.vhd"
check "oserdese2_10to1.v"  "/f/FPGA_Work/hdmi_board_bringup_v1/fpga/rtl/oserdese2_10to1.v"
check "hdmi_colorbar_720p_top.v" "/f/FPGA_Work/hdmi_board_bringup_v1/fpga/rtl/hdmi_colorbar_720p_top.v"
check "hdmi_colorbar_720p.xdc"   "/f/FPGA_Work/hdmi_board_bringup_v1/fpga/constrs/hdmi_colorbar_720p.xdc"

echo "== Qt runtime (host, offscreen check only) =="
# qmlscene/qmllint live under the Anaconda Qt runtime; adjust if your path differs.
check "qmlscene (anaconda)" \
  "/c/Users/shado/anaconda3/Library/bin/qmlscene.exe" \
  "/c/ProgramData/anaconda3/Library/bin/qmlscene.exe"
check "qmllint (anaconda)" \
  "/c/Users/shado/anaconda3/Library/bin/qmllint.exe" \
  "/c/ProgramData/anaconda3/Library/bin/qmllint.exe"

echo "== frozen UI =="
check "Main.qml" "/f/FPGA_Work/hdmi_ui_v1_1/app/qml/Main.qml"

if [ "$fail" -ne 0 ]; then
  echo "RESULT: 00_host_verify FAIL (see FAIL lines above)"
  exit 1
fi
echo "RESULT: 00_host_verify PASS"
