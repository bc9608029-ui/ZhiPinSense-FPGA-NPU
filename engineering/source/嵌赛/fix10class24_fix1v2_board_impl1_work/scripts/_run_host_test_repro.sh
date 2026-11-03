#!/bin/bash
# 复验：用重建的二进制跑 v1 + v2，期望各 pass=7 fail=0
set -e
cd "$(dirname "$0")/.."
BIN=host_tests/bin/test_radioml_independent_rx
ROOT=/mnt/f/嵌赛
V1=$ROOT/fix10class24_independent_rx_delivery_fix1_work
V2=$ROOT/fix10class24_waveform_correct_v2_work
rm -rf host_tests/bin/out_v1_rebuild host_tests/bin/out_v2_rebuild
echo "=========== v1 ==========="
$BIN --tx-dir $V1/tx_package --reference-tsv $V1/replay_out/independent_rx_replay.tsv \
     --reference-layers $V1/replay_out/layers --out-dir host_tests/bin/out_v1_rebuild
echo "V1_RC=$?"
echo "=========== v2 ==========="
$BIN --tx-dir $V2/tx_package --reference-tsv $V2/replay_out/independent_rx_replay.tsv \
     --reference-layers $V2/replay_out/layers --out-dir host_tests/bin/out_v2_rebuild
echo "V2_RC=$?"
