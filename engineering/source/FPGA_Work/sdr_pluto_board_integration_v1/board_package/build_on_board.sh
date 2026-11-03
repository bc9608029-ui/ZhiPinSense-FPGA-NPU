#!/usr/bin/env bash
# Native board (aarch64) build of the Gate 1-5 programs, against libiio.
#
# Usage:   ./build_on_board.sh [g++]
#   arg1          compiler (default: g++)
#   CXX           same as arg1 (env fallback)
#   LIBIIO_CFLAGS / LIBIIO_LIBS   override pkg-config detection when set
#   IIO_VERBOSE=1 to print the detected libiio flags
#
# Every gate program is built with -DSDR_ADAPTER_HAVE_LIBIIO and links the real
# libiio backend (pluto_device_libiio.cpp).  There is no mock fallback on board.
# Output: board_package/bin/{board_detect_pluto,board_rx_only,
#                            board_digital_loopback,board_rf_loopback,
#                            board_resampler_test}
set -euo pipefail
cd "$(dirname "$0")"

CXX="${1:-${CXX:-g++}}"

# ---- libiio detection (pkg-config, with a plain -liio fallback) ---------------
if [ -n "${LIBIIO_CFLAGS:-}" ] && [ -n "${LIBIIO_LIBS:-}" ]; then
    IIO_CFLAGS="$LIBIIO_CFLAGS"
    IIO_LIBS="$LIBIIO_LIBS"
elif pkg-config --exists libiio 2>/dev/null; then
    IIO_CFLAGS="$(pkg-config --cflags libiio)"
    IIO_LIBS="$(pkg-config --libs libiio)"
elif pkg-config --exists iio 2>/dev/null; then
    IIO_CFLAGS="$(pkg-config --cflags iio)"
    IIO_LIBS="$(pkg-config --libs iio)"
else
    IIO_CFLAGS=""
    IIO_LIBS="-liio"
fi
if [ -n "${IIO_VERBOSE:-}" ]; then
    echo "libiio CFLAGS: $IIO_CFLAGS"
    echo "libiio LIBS : $IIO_LIBS"
fi

COMMON="-std=gnu++17 -O2 -Wall -Wextra -Werror -DSDR_ADAPTER_HAVE_LIBIIO -I../sdr_adapter"
SRC="../sdr_adapter/pluto_device_libiio.cpp \
     ../sdr_adapter/pluto_tx.cpp \
     ../sdr_adapter/sample_rate_negotiate.cpp \
     ../sdr_adapter/resampler.cpp"

mkdir -p bin
rc=0
for prog in board_detect_pluto board_rx_only board_digital_loopback \
            board_rf_loopback board_resampler_test; do
    echo "== build $prog =="
    # shellcheck disable=SC2086
    if $CXX $COMMON $IIO_CFLAGS "$prog.cpp" $SRC $IIO_LIBS -o "bin/$prog"; then
        echo "   OK -> bin/$prog"
    else
        echo "   BUILD FAILED: $prog"; rc=1
    fi
done

if [ $rc -eq 0 ]; then
    echo "build_on_board.sh: all 5 gate programs built -> board_package/bin/"
else
    echo "build_on_board.sh: one or more builds failed" >&2
fi
exit $rc
