#!/usr/bin/env bash
# build_on_board.sh — build & run the HDMI instrument-UI PS programs ON the board.
#
# Runs ON the board (native aarch64 Linux).  NO iCraft / NPU dependency: the phase
# programs link only the safe direct framebuffer backend + the software UI, which
# talk to /dev/udmabuf0 + /dev/mem directly.  Only libc is required.
#
# v3 scope: phase2 (UI render) and phase3 (touch).  phase1b/phase1c are v2 assets
# and are not built here.
#
# Usage:
#   ./build_on_board.sh                     # CMake build (preferred)
#   ./build_on_board.sh g++                 # direct g++ fallback (no CMake)
#   ./build_on_board.sh run <phase> [args]  # run phase2 | phase3
#
#   Examples:
#     ./build_on_board.sh run phase2 -1 20 -1   # animate Top-1, cycle pages, 20 fps
#     ./build_on_board.sh run phase2 7 20 0     # pin 16QAM, Overview page, 20 fps
#     ./build_on_board.sh run phase3 30         # touch detect / page switch, 30 fps
#
#   RUN_TIMEOUT=600 ./build_on_board.sh run phase2 -1 20 -1
#       # wrap the program in `timeout --kill-after=5s 600` so a hang is killed.
#
# The frame_ctrl version gate runs INSIDE every program before any /dev/mem write,
# so a wrong bitstream can never be scribbled on.  Needs root for /dev/mem.

set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-cmake}"

BACKEND_SRCS="direct_framebuffer_backend.cpp"
UI_SRCS="font.cpp ui_renderer.cpp model_contract.cpp touch.cpp"

compile_gxx() {
    # $1 = output binary, $2 = source file.
    g++ -std=gnu++17 -O2 -Wall -Wextra "$2" $BACKEND_SRCS $UI_SRCS -o "$1"
}

case "$MODE" in
  cmake|--cmake)
    rm -rf build
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build -j"$(nproc 2>/dev/null || echo 4)"
    echo "built: build/phase2_ui_render"
    echo "built: build/phase3_touch_test"
    ;;

  g++|--g++)
    # Direct compile fallback.  No external libraries — just backend + UI + libc.
    compile_gxx phase2_ui_render phase2_ui_render.cpp
    compile_gxx phase3_touch_test phase3_touch_test.cpp
    echo "built: phase2_ui_render"
    echo "built: phase3_touch_test"
    ;;

  run|--run)
    PHASE="${2:-phase2}"
    shift 2 || true
    case "$PHASE" in
      phase2) BIN="phase2_ui_render" ;;
      phase3) BIN="phase3_touch_test" ;;
      *) echo "unknown phase: $PHASE (use phase2|phase3)" >&2; exit 1 ;;
    esac
    if [ -x "./build/$BIN" ]; then BIN="./build/$BIN"; fi

    # --- pre-run sanity check: refuse to launch into a missing device ---------
    if [ ! -e /dev/udmabuf0 ] || [ ! -e /sys/class/u-dma-buf/udmabuf0/phys_addr ] || [ ! -e /dev/mem ]; then
      echo "FAIL: /dev/udmabuf0, /sys/class/u-dma-buf/udmabuf0/phys_addr, and /dev/mem" >&2
      echo "      are all required. Load u-dma-buf and run as root (sudo)." >&2
      exit 1
    fi

    RUN_TIMEOUT="${RUN_TIMEOUT:-0}"   # 0 = interactive until Ctrl-C
    echo "running: $BIN $* (RUN_TIMEOUT=${RUN_TIMEOUT}s; 0 = interactive)"
    if [ "$RUN_TIMEOUT" -gt 0 ] && command -v timeout >/dev/null 2>&1; then
      timeout --kill-after=5s "$RUN_TIMEOUT" "$BIN" "$@"
    elif [ "$RUN_TIMEOUT" -gt 0 ]; then
      echo "WARN: 'timeout' not found; running without a time limit" >&2
      "$BIN" "$@"
    else
      "$BIN" "$@"
    fi
    rc=$?

    echo "POST-RUN_SHELL_OK (program exited rc=$rc)"
    exit "$rc"
    ;;

  *)
    echo "usage: $0 [cmake|g++|run <phase2|phase3> [args]]" >&2
    exit 1
    ;;
esac
