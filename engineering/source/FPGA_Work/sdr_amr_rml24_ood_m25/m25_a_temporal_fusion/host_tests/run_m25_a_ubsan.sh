#!/usr/bin/env bash
# run_m25_a_ubsan.sh -- build + run the M25-A host test under UBSan (undefined only).
# M25_SKIP_ALLOC_TEST disables the scoped global-new counter.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O1 -g -fsanitize=undefined -fno-omit-frame-pointer -DM25_SKIP_ALLOC_TEST -I../sdr_adapter"

mkdir -p ../build/m25
"$CXX" $FLAGS test_m25_a.cpp ../sdr_adapter/m25_temporal_fusion.cpp -o ../build/m25/test_m25_a_ubsan

UBSAN_OPTIONS=print_stacktrace=1 \
../build/m25/test_m25_a_ubsan

echo "M25_A_UBSAN_OK"
