#!/usr/bin/env bash
# run_m25_temporal_fusion_replay.sh -- build + run the M25-A logits replay tool.
#
# Runs the built-in deterministic demo stream (glitch + real switch) and, if a
# JSONL file is given as $1, replays that stream too.  Never touches the board.
set -euo pipefail
cd "$(dirname "$0")/.."   # project root: m25_a_temporal_fusion

./host_tools/build_m25_temporal_fusion_replay.sh

echo "== M25-A replay: built-in demo =="
./build/m25/m25_temporal_fusion_replay --demo

if [[ $# -ge 1 && -n "$1" ]]; then
  echo "== M25-A replay: $1 =="
  ./build/m25/m25_temporal_fusion_replay --jsonl "$1"
fi

echo "RUN_M25_TEMPORAL_FUSION_REPLAY_OK"
