#!/usr/bin/env bash
# build_m24_replay.sh -- build the M24-A offline IQ replay tool.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../sdr_adapter"

mkdir -p ../build/m24
"$CXX" $FLAGS m24_replay.cpp -o ../build/m24/m24_replay

echo "BUILD_M24_REPLAY_OK"
