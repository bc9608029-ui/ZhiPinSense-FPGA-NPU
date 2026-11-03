#!/usr/bin/env bash
# 06_collect_diagnostics.sh — collect board diagnostics into a dated directory.
# Runs ON the board.  Safe (read-only); no writes to permanent config.
set -u

OUT="/tmp/hdmi_diag_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
cd "$OUT" || exit 1

{
  echo "===== uname ====="; uname -a
  echo "===== compatible ====="; cat /proc/device-tree/compatible 2>/dev/null; echo
  echo "===== cmdline ====="; cat /proc/cmdline
  echo "===== cpuinfo ====="; cat /proc/cpuinfo | head -20
  echo "===== memory ====="; cat /proc/meminfo | head -8
  echo "===== dmesg (tail) ====="; dmesg | tail -80
  echo "===== usb ====="; lsusb 2>/dev/null || cat /proc/bus/usb/devices 2>/dev/null
  echo "===== input ====="; cat /proc/bus/input/devices 2>/dev/null
  echo "===== /dev/input ====="; ls -l /dev/input/ 2>/dev/null
  echo "===== udmabuf ====="; ls -l /dev/udmabuf* 2>/dev/null
  echo "===== fb/dri (expected absent) ====="; ls -l /dev/fb* /dev/dri/* 2>/dev/null
} > system.txt 2>&1

# Register peek (frame_ctrl base 0x40080000) if devmem exists.
if command -v devmem2 >/dev/null 2>&1; then
  for a in 0x40080000 0x40080054; do echo "$a = $(devmem2 $a 2>/dev/null)"; done > registers.txt 2>&1
elif command -v devmem >/dev/null 2>&1; then
  for a in 0x40080000 0x40080054; do echo "$a = $(devmem $a 2>/dev/null)"; done > registers.txt 2>&1
fi

echo "Diagnostics written to $OUT"
ls -l "$OUT"
