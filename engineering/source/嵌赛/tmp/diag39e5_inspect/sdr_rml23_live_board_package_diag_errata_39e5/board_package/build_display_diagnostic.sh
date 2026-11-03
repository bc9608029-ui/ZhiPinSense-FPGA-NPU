#!/usr/bin/env bash
# Native board (aarch64) build of the M18-0 display root-cause diagnostic tool
# (board_display_diagnostic).  iCraft-free and libiio-free: plain g++, no cmake,
# no pkg-config.  It links only the safe framebuffer backend + the pure
# display-diagnostic logic (no font atlas / UI render, since it draws solid
# colours only).
#
# A stale install is removed BEFORE the build so a failed build can never leave an
# old binary that masquerades as this round's success.
#
# Usage:   ./build_display_diagnostic.sh [compiler]
#   arg1          compiler (default: g++)
#   CXX           same as arg1 (env fallback)
set -euo pipefail
cd "$(dirname "$0")"
PKG_ROOT="$(cd .. && pwd)"
INSTALL_BIN="$PKG_ROOT/bin"

CXX="${1:-${CXX:-g++}}"

COMMON=(-std=gnu++17 -O2 -Wall -Wextra -Werror -I. -I../ui_sw)
SRC=(../ui_sw/direct_framebuffer_backend.cpp
     ../ui_sw/display_diagnostic.cpp)

TARGET="board_display_diagnostic"

rm -f "$INSTALL_BIN/$TARGET"
mkdir -p "$INSTALL_BIN"
TMP="$INSTALL_BIN/.$TARGET.tmp.$$"

if "$CXX" "${COMMON[@]}" board_display_diagnostic.cpp "${SRC[@]}" -o "$TMP"; then
    mv "$TMP" "$INSTALL_BIN/$TARGET"
    echo "DISPLAY_DIAGNOSTIC_BUILD result=PASS binary=$INSTALL_BIN/$TARGET"
    exit 0
fi

rm -f "$TMP" "$INSTALL_BIN/$TARGET"
echo "DISPLAY_DIAGNOSTIC_BUILD result=FAIL" >&2
exit 1
