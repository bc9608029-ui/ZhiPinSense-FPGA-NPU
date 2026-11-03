#!/usr/bin/env bash
# build_on_board.sh -- RML23 (M29 Phase F5) board build entry point.
#
# Builds BOTH RML23 binaries from source ON the FMQL30TAI Linux image:
#   1. board_gate9_full_chain_rml23  (producer: SDR -> 24-class NPU -> 23-class merge
#                                     -> UI; links iCraft runtime + libiio)
#   2. board_ui_live_rml23           (23-class LIVE UI server; iCraft/libiio-free)
#
# The producer is built by board_package/build_npu_on_board.sh --gate9-rml23
# (needs LIBIIO_ROOT and the on-chip iCraft 3.39 cmake configs).  The UI server is
# built by board_package/build_ui_live_rml23.sh (plain g++).  Both auto-install
# into the package top-level bin/.
#
# Usage (on board):
#   LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./scripts/build_on_board.sh
#   LIBIIO_ROOT=... ICRAFT_CMAKE_DIR=/usr/cmake ./scripts/build_on_board.sh
#
# Any failure returns non-zero (each sub-build already prints its own
# NPU_BUILD_RESULT / UI_BUILD_RESULT result=FAIL line).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "== RML23 build: producer board_gate9_full_chain_rml23 =="
"$ROOT/board_package/build_npu_on_board.sh" --gate9-rml23

echo "== RML23 build: UI server board_ui_live_rml23 =="
"$ROOT/board_package/build_ui_live_rml23.sh"

echo "RML23_BUILD_RESULT result=PASS producer=$ROOT/bin/board_gate9_full_chain_rml23 ui=$ROOT/bin/board_ui_live_rml23"
