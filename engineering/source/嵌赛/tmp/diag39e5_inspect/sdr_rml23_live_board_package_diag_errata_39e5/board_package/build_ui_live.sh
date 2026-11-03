#!/usr/bin/env bash
# Native board (aarch64) build of the twelve-class LIVE UI server
# (board_ui_live_12class).  This is the receiving half of the Gate 8 / Gate 9 ->
# screen link: an AF_UNIX SOCK_STREAM server that parses result_frame_v2 JSON-lines
# and renders the latest legal frame to the HDMI framebuffer (Style A, double
# buffer).
#
# iCraft-free and libiio-free: plain g++, no cmake, no pkg-config.  The server
# never touches the NPU / libiio, so it needs no on-chip SDK and no libiio.
#
# On success the binary is installed into the package top-level bin/ (the directory
# the run_ui_live.sh script loads from via require_bin), and a stale install is
# removed BEFORE the build so a failed build can never leave an old binary that
# masquerades as this round's success.
#
# Usage:   ./build_ui_live.sh [compiler]
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

TARGET="board_ui_live_12class"
CTL_TARGET="board_mode_ctl"

# Remove the stale install BEFORE building, so a failed build cannot leave an old
# binary that looks like this round's success.
rm -f "$INSTALL_BIN/$TARGET" "$INSTALL_BIN/$CTL_TARGET"

mkdir -p "$INSTALL_BIN"
TMP="$INSTALL_BIN/.$TARGET.tmp.$$"
CTL_TMP="$INSTALL_BIN/.$CTL_TARGET.tmp.$$"

# Build BOTH products before installing either, so a control-client failure can
# never leave a half-updated pair.
if "$CXX" "${COMMON[@]}" board_ui_live_12class.cpp "${SRC[@]}" -o "$TMP" &&
   "$CXX" "${COMMON[@]}" board_mode_ctl.cpp -o "$CTL_TMP"; then
    mv "$TMP" "$INSTALL_BIN/$TARGET"
    mv "$CTL_TMP" "$INSTALL_BIN/$CTL_TARGET"
    echo "UI_BUILD_RESULT result=PASS binary=$INSTALL_BIN/$TARGET ctl=$INSTALL_BIN/$CTL_TARGET"
    exit 0
fi

# Fail closed: never leave a product for this target on a failed build.
rm -f "$TMP" "$CTL_TMP" "$INSTALL_BIN/$TARGET" "$INSTALL_BIN/$CTL_TARGET"
echo "UI_BUILD_RESULT result=FAIL" >&2
exit 1
