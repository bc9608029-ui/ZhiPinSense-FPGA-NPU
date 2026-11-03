#!/usr/bin/env bash
# Native board (aarch64) build of the twelve-class NPU gates (Gate 7 / Gate 9),
# against the on-chip iCraft 3.39 SDK.  Run this ON the FMQL30TAI Linux image
# after the bitstream is confirmed.
#
#   Gate 7  board_gate7_12class_npu         NPU only (iCraft backends, no libiio)
#   Gate 9  board_gate9_full_chain_12class  NPU + libiio (full SDR -> NPU -> UI)
#   Gate 9R board_gate9_full_chain_rml23    NPU + libiio (full SDR -> 24-class NPU
#                                             -> AM-SSB merge -> 23-class UI; M29 F5)
#   Gate 10 board_gate10_selftest_12class   NPU + libiio (12-class RF self-test)
#
# The libiio / header-only gates (Gate 6 / Gate 8) are built by build_on_board.sh
# (direct g++) instead.
#
# Each gate builds in its OWN directory so building one never deletes the other's
# product:
#   --gate7-only  ->  build_gate7/board_gate7_12class_npu
#   --gate9       ->  build_gate9/board_gate9_full_chain_12class
#   --gate9-rml23 ->  build_gate9_rml23/board_gate9_full_chain_rml23
# On success the binary is auto-installed into the package top-level bin/ (the
# directory the run_*.sh scripts load from), and a stale install for that gate is
# removed BEFORE the build so a failed build can never leave an old binary that
# looks like this round's success.  Success prints:
#   NPU_BUILD_RESULT gate=<7|9|9R|10> result=PASS binary=<absolute path>
#
# Gate 7 does NOT need libiio or pkg-config (the board has neither), so it is the
# default.  Gate 9 additionally links libiio, located by the explicit LIBIIO_ROOT
# prefix (the board has no pkg-config / system libiio):
#     LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64 ./build_npu_on_board.sh --gate9
#
# The on-chip iCraft 3.39 package installs its configs under /usr/cmake and
# imports Icraft::ZG330Backend / Icraft::HostBackend.  If cmake cannot find them,
# set the prefix explicitly:
#     ICRAFT_CMAKE_DIR=/usr/cmake ./build_npu_on_board.sh --gate7-only
#
# Usage:   ./build_npu_on_board.sh [--gate7-only | --gate9 | --gate9-rml23 | --gate10] [CMAKE_ARGS...]
#   --gate7-only   build Gate 7 only (default; no libiio, no pkg-config)
#   --gate9        build Gate 9 only; requires LIBIIO_ROOT
#   --gate9-rml23  build Gate 9 RML23 (23-class) only; requires LIBIIO_ROOT
#   --gate10       build Gate 10 only (12-class RF self-test); requires LIBIIO_ROOT
#   LIBIIO_ROOT    libiio prefix for Gate 9 / Gate 9R / Gate 10 (include/iio.h + lib/libiio.so)
#   ICRAFT_CMAKE_DIR  value for -DCMAKE_PREFIX_PATH (iCraft cmake configs)
#
# Any build failure returns non-zero (after printing NPU_BUILD_RESULT ... FAIL).
set -euo pipefail
cd "$(dirname "$0")"
BP_DIR="$(pwd)"
PKG_ROOT="$(cd .. && pwd)"
INSTALL_BIN="$PKG_ROOT/bin"

MODE="gate7"
CMAKE_PASSTHRU=()
for arg in "$@"; do
    case "$arg" in
        --gate7-only) MODE="gate7" ;;
        --gate9)      MODE="gate9" ;;
        --gate9-rml23) MODE="gate9_rml23" ;;
        --gate10)     MODE="gate10" ;;
        *)            CMAKE_PASSTHRU+=("$arg") ;;
    esac
done

# Gate 9 / Gate 9R / Gate 10 need the explicit libiio prefix; fail closed BEFORE
# touching anything.
if { [ "$MODE" = "gate9" ] || [ "$MODE" = "gate9_rml23" ] || [ "$MODE" = "gate10" ]; } \
   && [ -z "${LIBIIO_ROOT:-}" ]; then
    echo "ERROR: --$MODE requires LIBIIO_ROOT=/path/to/libiio" >&2
    echo "       e.g. LIBIIO_ROOT=/tmp/sdr_pluto_gate1_5/libiio-arm64" >&2
    exit 1
fi

# Optional iCraft cmake prefix (e.g. /usr/cmake).
CMAKE_ARGS=()
if [ -n "${ICRAFT_CMAKE_DIR:-}" ]; then
    CMAKE_ARGS+=("-DCMAKE_PREFIX_PATH=${ICRAFT_CMAKE_DIR}")
fi

# Per-gate isolated build dir + target name (never share build/).
case "$MODE" in
    gate7)  BUILD_DIR="build_gate7";  TARGET="board_gate7_12class_npu";         GATE="7" ;;
    gate9)  BUILD_DIR="build_gate9";  TARGET="board_gate9_full_chain_12class";  GATE="9" ;;
    gate9_rml23) BUILD_DIR="build_gate9_rml23"; TARGET="board_gate9_full_chain_rml23"; GATE="9R" ;;
    gate10) BUILD_DIR="build_gate10"; TARGET="board_gate10_selftest_12class";   GATE="10" ;;
esac

case "$MODE" in
    gate9)  CONFIGURE=(-DCMAKE_BUILD_TYPE=Release -DBUILD_GATE9=ON  "-DLIBIIO_ROOT=${LIBIIO_ROOT}") ;;
    gate9_rml23) CONFIGURE=(-DCMAKE_BUILD_TYPE=Release -DBUILD_GATE9_RML23=ON "-DLIBIIO_ROOT=${LIBIIO_ROOT}") ;;
    gate10) CONFIGURE=(-DCMAKE_BUILD_TYPE=Release -DBUILD_GATE10=ON "-DLIBIIO_ROOT=${LIBIIO_ROOT}") ;;
    *)      CONFIGURE=(-DCMAKE_BUILD_TYPE=Release -DBUILD_GATE9=OFF) ;;
esac

# Remove the stale install BEFORE building, so a failed build cannot leave an old
# binary that masquerades as this round's success.
rm -f "$INSTALL_BIN/$TARGET"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

if cmake .. "${CONFIGURE[@]}" "${CMAKE_ARGS[@]}" "${CMAKE_PASSTHRU[@]}" \
     && make -j"$(nproc)" "$TARGET" \
     && [ -f "$TARGET" ]; then
    mkdir -p "$INSTALL_BIN"
    cp "$TARGET" "$INSTALL_BIN/$TARGET"
    echo "NPU_BUILD_RESULT gate=$GATE result=PASS binary=$INSTALL_BIN/$TARGET"
    exit 0
fi

# Fail closed: never leave a product for this gate on a failed build.
rm -f "$INSTALL_BIN/$TARGET"
echo "NPU_BUILD_RESULT gate=$GATE result=FAIL" >&2
exit 1
