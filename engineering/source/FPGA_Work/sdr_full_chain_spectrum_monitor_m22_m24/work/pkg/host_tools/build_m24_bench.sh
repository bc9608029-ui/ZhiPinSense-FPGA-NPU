#!/usr/bin/env bash
# build_m24_bench.sh -- build the M24-A unified performance benchmark.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../sdr_adapter"

mkdir -p ../build/m24
"$CXX" $FLAGS m24_bench.cpp -o ../build/m24/m24_bench

echo "BUILD_M24_BENCH_OK"
