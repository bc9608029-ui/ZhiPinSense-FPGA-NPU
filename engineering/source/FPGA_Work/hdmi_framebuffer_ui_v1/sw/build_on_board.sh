#!/usr/bin/env bash
# build_on_board.sh — build & run phase1a_fb_test on the FMQL30TAI board.
#
# Runs ON the board (native aarch64 Linux).  The iCraft runtime is installed from
# the Icraft_*.deb package (3.36.0 for this board; audit copy was 3.33.1):
#   headers: /usr/include/icraft-xrt, /usr/include/icraft-backends, ...
#   libs   : /usr/lib/aarch64-linux-gnu/libicraft_*.so
#   cmake  : /usr/cmake/icraft-*-config.cmake
#
# Usage:
#   ./build_on_board.sh                # CMake build (preferred)
#   ./build_on_board.sh g++            # direct g++ fallback (best-effort lib list)
#   ./build_on_board.sh run [pattern]  # run; pattern = checker|bars|gradient|red|green|blue
#
# If Device::Open fails with a permission error, the axi:// device access needs
# root: run the binary with sudo.

set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-cmake}"

case "$MODE" in
  cmake|--cmake)
    rm -rf build
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build -j"$(nproc 2>/dev/null || echo 4)"
    echo "built: build/phase1a_fb_test"
    ;;

  g++|--g++)
    # Direct compile fallback.  PREFER the CMake path above — this library list is
    # best-effort and depends on the exact iCraft SDK link closure (the CMake
    # find_package targets encode it correctly and transitively).
    g++ -std=gnu++17 -DUSE_ZG330_BACKEND -O2 \
        -I/usr/include \
        phase1a_fb_test.cpp -o phase1a_fb_test \
        -L/usr/lib/aarch64-linux-gnu \
        -licraft_zg330backend -licraft_xrt -licraft_xir -licraft_utils \
        -laxizg330aiu -lirpc_core -lpthread -ldl
    echo "built: phase1a_fb_test"
    ;;

  run|--run)
    PATTERN="${2:-checker}"
    BIN="${BIN:-}"
    if [ -z "$BIN" ]; then
      if [ -x ./build/phase1a_fb_test ]; then BIN=./build/phase1a_fb_test
      else                                   BIN=./phase1a_fb_test
      fi
    fi
    echo "running: $BIN $PATTERN"
    echo "(if it fails to open the device, retry with: sudo $BIN $PATTERN)"
    "$BIN" "$PATTERN"
    ;;

  *)
    echo "usage: $0 [cmake|g++|run [pattern]]" >&2
    exit 1
    ;;
esac
