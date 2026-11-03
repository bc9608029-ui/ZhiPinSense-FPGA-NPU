#!/usr/bin/env bash
# build_on_board.sh — build & run the v5_visual HDMI display PS tests on the board.
#
# Runs ON the board (native aarch64 Linux).  NO iCraft / NPU dependency: the phase
# programs link only the safe direct framebuffer backend (direct_framebuffer_backend)
# plus the device-independent Style A UI render layer (ui_render + font atlas), and
# talk to /dev/udmabuf0 + /dev/mem directly.  Only libc is required.
#
# Usage:
#   ./build_on_board.sh                     # CMake build of all tests (preferred)
#   ./build_on_board.sh g++                 # direct g++ fallback (no CMake)
#   ./build_on_board.sh run <phase> [args]  # run one test: phase1b|phase1c|phase2|phase3
#
#   Examples:
#     ./build_on_board.sh run phase1b 0 60        # moving bar, forever, 60 fps
#     ./build_on_board.sh run phase1c 600 60      # rotating patterns, 10 min, 60 fps
#     ./build_on_board.sh run phase2 -1 20        # Style A UI render, animate top-1, 20 fps
#     ./build_on_board.sh run phase3 30           # touch detect / page switch, 30 fps
#
#   RUN_TIMEOUT=600 ./build_on_board.sh run phase1c 0 60
#       # wrap the program in `timeout --kill-after=5s 600` so a hang is killed.
#
# The frame_ctrl version gate runs INSIDE every program before any /dev/mem write,
# so a wrong bitstream can never be scribbled on.  Needs root for /dev/mem.

set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-cmake}"

BIN_MAP_phase1b="phase1b_doublebuf_test"
BIN_MAP_phase1c="phase1c_dynamic_test"
BIN_MAP_phase2="phase2_ui_render"
BIN_MAP_phase3="phase3_touch_test"

ALL_BINS="phase1b_doublebuf_test phase1c_dynamic_test phase2_ui_render phase3_touch_test"

# Style A UI render layer (device-independent; also used by host_screenshot.cpp).
UI_SRCS="font_atlas.cpp font_atlas_data.cpp ui_render.cpp"

compile_gxx() {
    # $1 = output binary, $2 = source file.  Links the backend + UI render sources.
    g++ -std=gnu++17 -O2 -Wall -Wextra "$2" direct_framebuffer_backend.cpp $UI_SRCS -o "$1"
}

case "$MODE" in
  cmake|--cmake)
    rm -rf build
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build -j"$(nproc 2>/dev/null || echo 4)"
    for b in $ALL_BINS; do echo "built: build/$b"; done
    ;;

  g++|--g++)
    # Direct compile fallback.  No external libraries — just the backend + libc.
    compile_gxx phase1b_doublebuf_test phase1b_doublebuf_test.cpp
    compile_gxx phase1c_dynamic_test   phase1c_dynamic_test.cpp
    compile_gxx phase2_ui_render       phase2_ui_render.cpp
    compile_gxx phase3_touch_test       phase3_touch_test.cpp
    for b in $ALL_BINS; do echo "built: $b"; done
    ;;

  run|--run)
    PHASE="${2:-phase1b}"
    shift 2 || true
    VAR="BIN_MAP_$PHASE"
    BIN="${!VAR:-}"
    if [ -z "$BIN" ]; then
      echo "unknown phase: $PHASE (use phase1b|phase1c|phase2|phase3)" >&2
      exit 1
    fi
    # CMake puts binaries in ./build/; the g++ fallback puts them in ./.
    if [ -x "./build/$BIN" ]; then BIN="./build/$BIN"; elif [ -x "./$BIN" ]; then BIN="./$BIN"; fi

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

    # --- post-run shell-recovery check --------------------------------------
    if echo "shell-ok" >/dev/null 2>&1; then
      echo "POST-RUN_SHELL_OK (shell responsive; program exited rc=$rc)"
    else
      echo "POST-RUN_SHELL_HUNG" >&2
    fi
    exit "$rc"
    ;;

  *)
    echo "usage: $0 [cmake|g++|run <phase> [args]]" >&2
    exit 1
    ;;
esac
