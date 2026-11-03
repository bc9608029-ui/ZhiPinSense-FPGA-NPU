#!/usr/bin/env bash
# -fsyntax-only checks for the iCraft board sources (Gate 7 / Gate 9 / Gate 10)
# against the iCraft 3.39 headers.  This verifies HOST-SIDE SYNTAX ONLY (no link,
# no board toolchain): a board link/run is still required on hardware -- "host
# syntax verified" is NOT a board build pass.
#
# The iCraft headers are passed via -isystem so their own warnings are suppressed
# and any -Wall -Wextra -Werror diagnostic can only come from OUR sources.  No
# libiio header is needed here: pluto::make_device / pluto::DeviceStateGuard /
# pluto::PlutoTx are declared header-only (the libiio-backed make_device lives in
# pluto_device_libiio.cpp, which is compiled only on the board with
# -DSDR_ADAPTER_HAVE_LIBIIO).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$HERE/../board_package"
INC="${ICRAFT_INCLUDE:-/mnt/f/嵌赛/audit/icraft_3_39/usr/include}"

if [ ! -d "$INC/icraft-backends" ]; then
    echo "ERROR: iCraft headers not found at $INC" >&2
    echo "       Set ICRAFT_INCLUDE=/path/to/icraft_3_39/usr/include" >&2
    exit 1
fi

FLAGS="-std=gnu++17 -fsyntax-only -Wall -Wextra -Werror"
ISYS="-isystem $INC -I$PKG -I$HERE/../sdr_adapter -I$HERE/../ui_sw"

g++ $FLAGS $ISYS "$PKG/board_gate7_12class_npu.cpp"
echo "gate7: syntax OK"

g++ $FLAGS $ISYS "$PKG/board_gate9_full_chain_12class.cpp"
echo "gate9: syntax OK"

g++ $FLAGS $ISYS "$PKG/board_gate10_selftest_12class.cpp"
echo "gate10: syntax OK"

# The FULL pilot1 capture runner (board-only path): -fsyntax-only so a declaration-order
# bug in the runner itself (e.g. a helper used before its definition) is caught here,
# before any board aarch64 build.  (Review 39e5 Blocker 1.)
g++ $FLAGS $ISYS "$HERE/pilot1_capture_runner_syntax.cpp"
echo "pilot1_capture_runner: syntax OK"

g++ $FLAGS $ISYS "$PKG/board_gate9_full_chain_rml23.cpp"
echo "gate9_rml23: syntax OK"
