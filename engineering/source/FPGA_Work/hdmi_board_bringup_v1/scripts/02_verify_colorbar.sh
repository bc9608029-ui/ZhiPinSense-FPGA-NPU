#!/usr/bin/env bash
# 02_verify_colorbar.sh — confirm the 720p colour bar appears on HDMI.
#
# This is a checklist script; the actual "bar is visible" check is a human
# observation.  It records the expected result so the pass/fail is explicit.
set -u

echo "After the temporary JTAG load (01), confirm on the HDMI monitor:"
echo
echo "  EXPECTED: an 8-colour vertical bar pattern, ordered left to right"
echo "            white / yellow / cyan / green / magenta / red / blue / black."
echo "  RESOLUTION: 1280x720 @ 60 Hz (monitor OSD should report ~720p60)."
echo
echo "On the board:"
echo "  LED[0] ON  = both MMCMs locked (clock chain good)."
echo "  LED[1] BLINK ~1 Hz = pixel clock running."
echo
read -r -p "Is the 8-colour bar visible and stable (no flicker)? [y/N] " ans
if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
  echo "RESULT: 02_verify_colorbar PASS"
else
  echo "RESULT: 02_verify_colorbar FAIL"
  echo "  -> if blank: re-check JTAG cable, hw target, and that LED[0] is ON."
  echo "  -> if flicker: this is a timing/clock issue; stop and report, do NOT flash."
  echo "  -> if heat/smell/abnormal current at any point: CUT POWER NOW."
  exit 1
fi
