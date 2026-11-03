#!/usr/bin/env bash
# Host x86_64 compile+link check for the Gate 1-5 board programs against the
# REAL libiio sysroot (libiio 0.26).  This proves the corrected
# pluto_device_libiio.cpp (debug-attr loopback, channel-attr control plane,
# interleaved-int16 stream, lazy RX buffer) links against the actual libiio ABI
# -- it is NOT a board run and does NOT claim any Gate result.
#
# Usage (inside WSL):  ./link_libiio_host_check.sh [sysroot]
#   sysroot = extracted libiio sysroot (default: $HOME/iio_work/sysroot)
set -euo pipefail

SYSROOT="${1:-$HOME/iio_work/sysroot}"
INC="-I$SYSROOT/usr/include"
LIB="-L$SYSROOT/usr/lib/x86_64-linux-gnu -liio \
  -Wl,-rpath-link,$SYSROOT/usr/lib/x86_64-linux-gnu"
COMMON="-std=gnu++17 -O2 -Wall -Wextra -Werror -DSDR_ADAPTER_HAVE_LIBIIO -I../sdr_adapter"
SRC="../sdr_adapter/pluto_device_libiio.cpp \
     ../sdr_adapter/pluto_tx.cpp \
     ../sdr_adapter/sample_rate_negotiate.cpp \
     ../sdr_adapter/resampler.cpp"
OUT="$HOME/iio_work/build"
mkdir -p "$OUT"

cd "$(dirname "$0")/../board_package"

for prog in board_detect_pluto board_rx_only board_digital_loopback \
            board_rf_loopback board_resampler_test; do
    echo "== link $prog (host, real libiio) =="
    # shellcheck disable=SC2086
    g++ $COMMON $INC "$prog.cpp" $SRC $LIB -o "$OUT/${prog}.host"
    echo "   OK -> $OUT/${prog}.host"
done

echo "link_libiio_host_check.sh: all 5 board programs linked against libiio OK"
