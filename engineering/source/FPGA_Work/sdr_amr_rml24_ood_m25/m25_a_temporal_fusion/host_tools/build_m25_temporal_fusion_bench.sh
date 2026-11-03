#!/usr/bin/env bash
# build_m25_temporal_fusion_bench.sh -- build the M25-A unified performance benchmark.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../sdr_adapter"

mkdir -p ../build/m25
"$CXX" $FLAGS m25_temporal_fusion_bench.cpp ../sdr_adapter/m25_temporal_fusion.cpp -o ../build/m25/m25_temporal_fusion_bench

echo "BUILD_M25_TEMPORAL_FUSION_BENCH_OK"
