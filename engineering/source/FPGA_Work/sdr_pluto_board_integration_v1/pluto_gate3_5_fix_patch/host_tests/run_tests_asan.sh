#!/usr/bin/env bash
# Build + run every host test under ASan + UBSan (and -Wall -Wextra -Werror).
# Sanitizer binaries are built into a native-WSL dir (not the 9p source tree) so
# ASan can map its shadow memory; outputs do not pollute the frozen tree.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
SAN="-fsanitize=address,undefined -fno-omit-frame-pointer"
FLAGS="-std=gnu++17 -Wall -Wextra -Werror -O1 -g $SAN -I../sdr_adapter"
OUT="${SAN_OUT:-$HOME/iio_work/asan}"
mkdir -p "$OUT"

build() { # $1 = src, extra sources...
    local name="$1"; shift
    "$CXX" $FLAGS "$name.cpp" "$@" -o "$OUT/$name"
}

build test_all            ../sdr_adapter/iq_source.cpp
build test_nco
build test_attr_routing
build test_receiver_scale
build test_rx_format
build test_resampler       ../sdr_adapter/resampler.cpp
build test_sample_rate_negotiate ../sdr_adapter/sample_rate_negotiate.cpp
build test_pluto_tx        ../sdr_adapter/pluto_tx.cpp
build test_device_state_guard

export ASAN_OPTIONS=detect_leaks=1
export UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1
for t in test_all test_nco test_attr_routing test_receiver_scale test_rx_format \
         test_resampler test_sample_rate_negotiate test_pluto_tx \
         test_device_state_guard; do
    echo "== run $t (ASan+UBSan) =="
    "$OUT/$t"
done

echo "run_tests_asan.sh: all suites passed under ASan+UBSan"
