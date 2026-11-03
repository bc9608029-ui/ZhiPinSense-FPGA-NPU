#!/bin/bash
# Offscreen GUI smoke test for constellation_viewer (task three).
# Success = QML loads without error (exit 124 from timeout = app alive 10s,
# empty log = no "QtQuick.Controls not installed" / "failed to load component").
set -u
cd /mnt/f/嵌赛/constellation_ui_prototype || { echo "CD_FAIL"; exit 2; }
QT_QPA_PLATFORM=offscreen timeout 10 ./build/constellation_viewer \
  --fixture-dir fixtures/valid --fps 1 > /tmp/gui_smoke.log 2>&1
code=$?
echo "EXIT=$code"
echo "LOG_BYTES=$(wc -c < /tmp/gui_smoke.log)"
echo "---LOG---"
cat /tmp/gui_smoke.log
