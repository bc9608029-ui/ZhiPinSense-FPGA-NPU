#!/usr/bin/env bash
# build_m25_temporal_fusion_replay.sh -- build the M25-A offline logits replay tool.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../sdr_adapter"

mkdir -p ../build/m25
"$CXX" $FLAGS m25_temporal_fusion_replay.cpp ../sdr_adapter/m25_temporal_fusion.cpp -o ../build/m25/m25_temporal_fusion_replay

echo "BUILD_M25_TEMPORAL_FUSION_REPLAY_OK"
