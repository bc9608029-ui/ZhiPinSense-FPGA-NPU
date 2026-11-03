#!/usr/bin/env bash
# Native board (aarch64) build of the libiio / header-only twelve-class gates.
#
#   Gate 6  board_gate6_sdr_preprocess   (libiio: Pluto RX -> fp32 tensor)
#   Gate 8  board_gate8_ui               (header-only: ResultFrame -> UI JSONL)
#   §九     board_calibrate_rec_scale    (libiio: receiver_scale calibration)
#
# The NPU gates (Gate 7 / Gate 9) need the iCraft backends and are built by
# build_npu_on_board.sh (via CMakeLists.txt) instead.
#
# Usage:   ./build_on_board.sh [compiler]
#   arg1          compiler (default: g++)
#   CXX           same as arg1 (env fallback)
#   LIBIIO_ROOT   explicit libiio prefix, e.g. /tmp/sdr_pluto_gate1_5/libiio-arm64
#                 -> -I<root>/include -L<root>/lib -liio -Wl,-rpath,<root>/lib.
#                 The board image has NO pkg-config and NO system libiio, so set
#                 LIBIIO_ROOT; it fails closed (exit 1, before compiling) if
#                 <root>/include/iio.h or <root>/lib/libiio.so is missing.
#                 (LIBIIO_CFLAGS / LIBIIO_LIBS still override flag detection for
#                 odd layouts; IIO_VERBOSE=1 prints the resolved flags.)
#
# Gate 6 is built with -DSDR_ADAPTER_HAVE_LIBIIO and links the real libiio
# backend (pluto_device_libiio.cpp); there is NO mock fallback on board.
# Gate 8 is header-only (chain_common + ui_report + unix_socket_sink) and links
# no libiio and no iCraft.
#
# Output: board_package/bin/{board_gate6_sdr_preprocess, board_gate8_ui,
#                             board_calibrate_rec_scale}
set -euo pipefail
cd "$(dirname "$0")"

CXX="${1:-${CXX:-g++}}"

# ---- libiio detection (explicit LIBIIO_ROOT preferred; pkg-config fallback) ---
# Arrays (not unquoted strings) so paths containing spaces survive word-splitting.
IIO_CFLAGS=()
IIO_LIBS=()
RPATH=()

if [ -n "${LIBIIO_ROOT:-}" ]; then
    inc="${LIBIIO_ROOT}/include"
    libdir="${LIBIIO_ROOT}/lib"
    if [ ! -f "$inc/iio.h" ]; then
        echo "ERROR: libiio header not found: $inc/iio.h" >&2
        echo "       (LIBIIO_ROOT=$LIBIIO_ROOT)" >&2
        exit 1
    fi
    if [ ! -f "$libdir/libiio.so" ] && [ ! -f "$libdir/libiio.a" ]; then
        echo "ERROR: libiio library not found: $libdir/libiio.so" >&2
        echo "       (LIBIIO_ROOT=$LIBIIO_ROOT)" >&2
        exit 1
    fi
    IIO_CFLAGS=(-I"$inc")
    IIO_LIBS=(-L"$libdir" -liio)
    RPATH=("-Wl,-rpath,$libdir")
elif [ -n "${LIBIIO_CFLAGS:-}" ] && [ -n "${LIBIIO_LIBS:-}" ]; then
    # Explicit flag override (legacy); caller is responsible for correctness.
    # shellcheck disable=SC2206
    IIO_CFLAGS=( $LIBIIO_CFLAGS )
    # shellcheck disable=SC2206
    IIO_LIBS=( $LIBIIO_LIBS )
elif command -v pkg-config >/dev/null 2>&1 && pkg-config --exists libiio 2>/dev/null; then
    # shellcheck disable=SC2206
    IIO_CFLAGS=( $(pkg-config --cflags libiio) )
    # shellcheck disable=SC2206
    IIO_LIBS=( $(pkg-config --libs libiio) )
elif command -v pkg-config >/dev/null 2>&1 && pkg-config --exists iio 2>/dev/null; then
    # shellcheck disable=SC2206
    IIO_CFLAGS=( $(pkg-config --cflags iio) )
    # shellcheck disable=SC2206
    IIO_LIBS=( $(pkg-config --libs iio) )
else
    # No pkg-config: assume system libiio (e.g. a host with libiio but no .pc).
    IIO_CFLAGS=()
    IIO_LIBS=(-liio)
fi

if [ -n "${IIO_VERBOSE:-}" ]; then
    echo "libiio CFLAGS: ${IIO_CFLAGS[*]:-}"
    echo "libiio LIBS : ${IIO_LIBS[*]:-}"
    echo "libiio RPATH : ${RPATH[*]:-}"
fi

COMMON=(-std=gnu++17 -O2 -Wall -Wextra -Werror -I../sdr_adapter)
SRC=(../sdr_adapter/pluto_device_libiio.cpp
     ../sdr_adapter/pluto_tx.cpp
     ../sdr_adapter/sample_rate_negotiate.cpp
     ../sdr_adapter/resampler.cpp)

mkdir -p bin
rc=0

echo "== build board_gate6_sdr_preprocess (libiio) =="
if "$CXX" "${COMMON[@]}" -DSDR_ADAPTER_HAVE_LIBIIO "${IIO_CFLAGS[@]}" \
     board_gate6_sdr_preprocess.cpp "${SRC[@]}" "${IIO_LIBS[@]}" "${RPATH[@]}" \
     -o bin/board_gate6_sdr_preprocess; then
    echo "   OK -> bin/board_gate6_sdr_preprocess"
else
    echo "   BUILD FAILED: board_gate6_sdr_preprocess"; rc=1
fi

echo "== build board_gate8_ui (header-only) =="
if "$CXX" "${COMMON[@]}" board_gate8_ui.cpp -o bin/board_gate8_ui; then
    echo "   OK -> bin/board_gate8_ui"
else
    echo "   BUILD FAILED: board_gate8_ui"; rc=1
fi

echo "== build board_calibrate_rec_scale (libiio, §九) =="
if "$CXX" "${COMMON[@]}" -DSDR_ADAPTER_HAVE_LIBIIO "${IIO_CFLAGS[@]}" \
     board_calibrate_rec_scale.cpp "${SRC[@]}" "${IIO_LIBS[@]}" "${RPATH[@]}" \
     -o bin/board_calibrate_rec_scale; then
    echo "   OK -> bin/board_calibrate_rec_scale"
else
    echo "   BUILD FAILED: board_calibrate_rec_scale"; rc=1
fi

if [ $rc -eq 0 ]; then
    echo "build_on_board.sh: Gate 6 + Gate 8 + calibrate built -> board_package/bin/"
else
    echo "build_on_board.sh: one or more builds failed" >&2
fi
exit $rc
