#!/usr/bin/env bash
# Native board (aarch64) build of the final raw-24 LIVE UI server. It parses the
# fail-closed rml24-final-chain-v1 record and renders classification, relative
# spectrum/waterfall, and recovered-IQ constellation pages.
#
# iCraft-free and libiio-free: plain g++, no cmake, no pkg-config.  The server
# never touches the NPU / libiio, so it needs no on-chip SDK and no libiio.
#
# This builds a distinct board_ui_live_rml24_final binary, so existing 12/23
# class UI installs are never overwritten.
#
# On success the binary is installed into the package top-level bin/ (the
# directory start_live_rml23.sh loads from via require_bin), and a stale install
# is removed BEFORE the build so a failed build can never leave an old binary
# that masquerades as this round's success.
#
# Usage:   ./build_ui_live_rml24_final.sh [compiler]
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
     ../ui_sw/ui_render.cpp
     ../ui_sw/waterfall_render.cpp)

TARGET="board_ui_live_rml24_final"

# Remove the stale install BEFORE building, so a failed build cannot leave an old
# binary that looks like this round's success.
rm -f "$INSTALL_BIN/$TARGET"

mkdir -p "$INSTALL_BIN"
TMP="$INSTALL_BIN/.$TARGET.tmp.$$"

if "$CXX" "${COMMON[@]}" board_ui_live_rml24_final.cpp "${SRC[@]}" -o "$TMP"; then
    mv "$TMP" "$INSTALL_BIN/$TARGET"
    echo "UI_BUILD_RESULT result=PASS binary=$INSTALL_BIN/$TARGET"
    exit 0
fi

# Fail closed: never leave a product for this target on a failed build.
rm -f "$TMP" "$INSTALL_BIN/$TARGET"
echo "UI_BUILD_RESULT result=FAIL" >&2
exit 1
