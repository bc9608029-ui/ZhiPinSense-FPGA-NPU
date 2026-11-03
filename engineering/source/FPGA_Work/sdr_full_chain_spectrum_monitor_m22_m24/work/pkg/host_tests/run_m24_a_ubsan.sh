#!/usr/bin/env bash
# run_m24_a_ubsan.sh -- build + run the M24-A host test under UBSan (undefined only).
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O1 -g -fsanitize=undefined -fno-omit-frame-pointer -I../sdr_adapter"

mkdir -p ../build/m24
"$CXX" $FLAGS test_m24_a.cpp -o ../build/m24/test_m24_a_ubsan

UBSAN_OPTIONS=print_stacktrace=1 \
../build/m24/test_m24_a_ubsan

echo "M24_A_UBSAN_OK"
