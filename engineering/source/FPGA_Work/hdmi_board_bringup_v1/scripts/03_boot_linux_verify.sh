#!/usr/bin/env bash
# 03_boot_linux_verify.sh — boot the stock Linux image and verify the display
# / input situation.  Runs ON the board (via serial console or SSH).
#
# Expected findings (from the shipped fmqlmp-verify.dtb):
#   - NO /dev/fb0 and NO /dev/dri/card0 (HDMI is PL pHDMI, not a framebuffer).
#   - usb@e0045000 is the OTG/ULPI controller behind the 4-port hub.
#   - udmabuf0 present (userspace contiguous DDR for the PL AXI master).
set -u

echo "== identity =="
uname -a || true
cat /proc/device-tree/compatible 2>/dev/null; echo || true

echo "== display backend (expected: absent) =="
ls -l /dev/fb0 /dev/dri/card0 2>/dev/null || echo "  no /dev/fb0, no /dev/dri/card0 (as expected: pHDMI, not framebuffer)"

echo "== udmabuf (expected: present) =="
ls -l /dev/udmabuf0 2>/dev/null || echo "  /dev/udmabuf0 not present"

echo "== usb =="
lsusb 2>/dev/null || cat /proc/bus/usb/devices 2>/dev/null || echo "  no lsusb"

echo "== input (see 04 for touch detail) =="
ls -l /dev/input/ 2>/dev/null || echo "  no /dev/input"

echo "== display registers (optional, needs devmem) =="
# frame_ctrl base 0x40080000; display-read-address reg 0x40080054.
if command -v devmem2 >/dev/null 2>&1; then devmem2 0x40080054 2>/dev/null; \
elif command -v devmem  >/dev/null 2>&1; then devmem  0x40080054 2>/dev/null; \
else echo "  devmem not available"; fi
