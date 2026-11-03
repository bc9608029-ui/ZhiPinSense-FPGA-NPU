#!/usr/bin/env bash
# build_m25_a.sh -- build the M25-A temporal fusion host test (release).
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../sdr_adapter"

mkdir -p ../build/m25
"$CXX" $FLAGS test_m25_a.cpp ../sdr_adapter/m25_temporal_fusion.cpp -o ../build/m25/test_m25_a

echo "BUILD_M25_A_OK"
