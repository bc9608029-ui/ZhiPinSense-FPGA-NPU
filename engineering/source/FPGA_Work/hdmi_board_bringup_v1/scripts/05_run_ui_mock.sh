#!/usr/bin/env bash
# 05_run_ui_mock.sh — run the UI with a Mock/JSONL data source and push a frame
# to the PL via the RGB565 path.  Runs ON the board.
#
# This stage requires the cross-built Qt app (pending-qt-build, see ../qt/).
# It renders the QML offscreen, converts to RGB565, writes the contiguous DDR
# buffer (udmabuf0) and writes register 0x40080054 = (buf_addr >> 3).
set -u

APP="/root/hdmi_ui_v1_1/hdmi_ui_v1_1"   # placeholder path of the cross-built app
if [ ! -x "$APP" ]; then
  echo "BLOCKED: cross-built Qt app not found at $APP."
  echo "  This is pending-qt-build (no aarch64 Qt in the provided toolchain)."
  echo "  See ../qt/README.md for what must be added before this stage can run."
  exit 2
fi

echo "== run UI (offscreen) with mock data source =="
QT_QPA_PLATFORM=offscreen "$APP" --source mock &

echo
echo "Expected on HDMI: the 10-class AMC UI rendered from mock ResultFrame data."
echo "The display is driven by the PL reading the RGB565 buffer the app writes"
echo "(register 0x40080054 = buffer_addr >> 3), NOT by any framebuffer."
echo
echo "This script is a placeholder until the Qt aarch64 build exists."
