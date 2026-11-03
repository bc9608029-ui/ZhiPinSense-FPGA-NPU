#!/usr/bin/env bash
# Native board (aarch64) build of the RML23 23-class LIVE UI server
# (board_ui_live_rml23).  This is the receiving half of the Gate 9 RML23 ->
# screen link: an AF_UNIX SOCK_STREAM server that parses "rml23-chain-v2"
# JSON-lines (result_frame_rml23_parse.hpp) and renders the latest legal 23-class
# frame to the HDMI framebuffer (Style A, double buffer).
#
# iCraft-free and libiio-free: plain g++, no cmake, no pkg-config.  The server
# never touches the NPU / libiio, so it needs no on-chip SDK and no libiio.
#
# Distinct from build_ui_live.sh (board_ui_live_12class): this builds ONLY the
# RML23 server, so a 12-class UI install is never overwritten.  The reverse
# control client (board_mode_ctl) is shared with the 12-class chain and is built
# by build_ui_live.sh; it is NOT rebuilt here.
#
# On success the binary is installed into the package top-level bin/ (the
# directory start_live_rml23.sh loads from via require_bin), and a stale install
# is removed BEFORE the build so a failed build can never leave an old binary
# that masquerades as this round's success.
#
# Usage:   ./build_ui_live_rml23.sh [compiler]
#   arg1          compiler (default: g++)
#   CXX           same as arg1 (env fallback)
set -euo pipefail
cd "$(dirname "$0")"
PKG_ROOT="$(cd .. && pwd)"
INSTALL_BIN="$PKG_ROOT/bin"

CXX="${1:-${CXX:-g++}}"

COMMON=(-std=gnu++17 -O2 -Wall -Wextra -Werror -I. -I../sdr_adapter -I../ui_sw)
SRC=(../ui_sw/direct_framebuffer_backend.cpp
     ../ui_sw/font_atlas.cpp
     ../ui_sw/font_atlas_data.cpp
     ../ui_sw/ui_render.cpp)

TARGET="board_ui_live_rml23"

# Remove the stale install BEFORE building, so a failed build cannot leave an old
# binary that looks like this round's success.
rm -f "$INSTALL_BIN/$TARGET"

mkdir -p "$INSTALL_BIN"
TMP="$INSTALL_BIN/.$TARGET.tmp.$$"

if "$CXX" "${COMMON[@]}" board_ui_live_rml23.cpp "${SRC[@]}" -o "$TMP"; then
    mv "$TMP" "$INSTALL_BIN/$TARGET"
    echo "UI_BUILD_RESULT result=PASS binary=$INSTALL_BIN/$TARGET"
    exit 0
fi

# Fail closed: never leave a product for this target on a failed build.
rm -f "$TMP" "$INSTALL_BIN/$TARGET"
echo "UI_BUILD_RESULT result=FAIL" >&2
exit 1
