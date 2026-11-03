#!/usr/bin/env bash
# run_m24_a_asan.sh -- build + run the M24-A host test under ASan (address only).
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O1 -g -fsanitize=address -fno-omit-frame-pointer -I../sdr_adapter"

mkdir -p ../build/m24
"$CXX" $FLAGS test_m24_a.cpp -o ../build/m24/test_m24_a_asan

ASAN_OPTIONS=detect_leaks=1 \
../build/m24/test_m24_a_asan

echo "M24_A_ASAN_OK"
