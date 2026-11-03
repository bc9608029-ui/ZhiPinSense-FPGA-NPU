#!/usr/bin/env bash
# 04_verify_touch.sh — check whether a USB touchscreen (if any is connected)
# enumerates as an input device.  Runs ON the board.
#
# Hardware is UNCONFIRMED: the manuals list no touch panel and the DT has no
# touch/HID node, but a USB HID touchscreen would normally appear via the
# generic usbhid -> hid-multitouch -> evdev path without a DT node.
set -u

echo "== input devices =="
cat /proc/bus/input/devices 2>/dev/null || echo "  no /proc/bus/input/devices"

echo "== event nodes =="
ls -l /dev/input/event* 2>/dev/null || echo "  no /dev/input/event*"

echo "== if evtest is present, tap the panel and watch for ABS_X/ABS_Y/BTN_TOUCH =="
if command -v evtest >/dev/null 2>&1; then
  echo "  run: evtest /dev/input/event<N>   (replace N with the touch node)"
else
  echo "  evtest not installed (apt-get install evtest, or read raw /dev/input/eventN)"
fi

echo
echo "If a touchscreen appears in /proc/bus/input/devices, record its event node"
echo "and hand it to the Qt evdevtouch plugin / manual evdev reader (see ../touch/)."
