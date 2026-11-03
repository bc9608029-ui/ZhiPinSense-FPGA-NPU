#!/usr/bin/env bash
# collect_logs.sh — gather board-side evidence for one bring-up phase.
#
# Run ON the board, from the sw/ directory.  Produces a timestamped directory of
# everything needed to judge PASS/FAIL and to attach to a bug report:
#   system info, iCraft runtime, dmesg tail, USB topology, input devices,
#   the phase program's captured stdout (if you saved it to a file), and the
#   sha256 of the program binary.
#
# Usage:
#   ./collect_logs.sh <phase> [program_stdout.log]
#
#   phase = phase2 | phase3
#   program_stdout.log = optional path to a file where you already captured the
#                        program's output (e.g. via `./build_on_board.sh run phase2 -1 20 -1 2>&1 | tee /tmp/phase2.log`)
#
# The program itself also runs fine under `script -c ... phaseN.typescript` to
# capture the full terminal session; point this script at that file.

set -u
cd "$(dirname "$0")"

PHASE="${1:?usage: $0 <phase> [stdout.log]}"
STDOUT_LOG="${2:-}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="logs_${PHASE}_${STAMP}"
mkdir -p "$OUT"

echo "collecting to: $OUT"

{
  echo "=== uname -a ==="
  uname -a
  echo
  echo "=== date ==="
  date
  echo
  echo "=== u-dma-buf (framebuffer) ==="
  ls -l /dev/udmabuf* 2>/dev/null || echo "(no /dev/udmabuf*)"
  echo "phys_addr: $(cat /sys/class/u-dma-buf/udmabuf0/phys_addr 2>/dev/null || echo unknown)"
  echo "size:      $(cat /sys/class/u-dma-buf/udmabuf0/size 2>/dev/null || echo unknown)"
  echo "sync node: $(ls /sys/class/u-dma-buf/udmabuf0/sync_for_device 2>/dev/null || echo absent)"
  echo
  echo "=== dmesg (tail 200) ==="
  dmesg 2>/dev/null | tail -n 200 || echo "(dmesg unavailable)"
  echo
  echo "=== USB topology ==="
  cat /proc/bus/usb/devices 2>/dev/null || echo "(/proc/bus/usb/devices unavailable)"
  echo
  echo "=== input devices ==="
  cat /proc/bus/input/devices 2>/dev/null || echo "(/proc/bus/input/devices unavailable)"
} > "$OUT/system.txt"

echo "written: $OUT/system.txt"

if [ -n "$STDOUT_LOG" ] && [ -f "$STDOUT_LOG" ]; then
  cp "$STDOUT_LOG" "$OUT/program_stdout.log"
  echo "written: $OUT/program_stdout.log (from $STDOUT_LOG)"
fi

# sha256 of the phase binary (build/ or cwd) + its source
BIN=""
for cand in "build/$PHASE"* "$PHASE"*; do
  [ -f "$cand" ] && [ -x "$cand" ] && BIN="$cand" && break
done
if [ -n "$BIN" ]; then
  sha256sum "$BIN" > "$OUT/binary.sha256"
  echo "written: $OUT/binary.sha256 ($BIN)"
fi
if [ -f "$PHASE"*.cpp ]; then
  sha256sum "$PHASE"*.cpp > "$OUT/source.sha256" 2>/dev/null
  echo "written: $OUT/source.sha256"
fi

# optional: the v2 bitstream sha256 (if it was copied onto the board)
find . /tmp -maxdepth 4 -name 'hdmi_framebuffer_720p_top_disable_icap.bit' 2>/dev/null | while read -r f; do
  sha256sum "$f"
done > "$OUT/bitstream.sha256" 2>/dev/null
[ -s "$OUT/bitstream.sha256" ] && echo "written: $OUT/bitstream.sha256" || rm -f "$OUT/bitstream.sha256"

echo "done. tar it with:  tar czf $OUT.tar.gz $OUT"
