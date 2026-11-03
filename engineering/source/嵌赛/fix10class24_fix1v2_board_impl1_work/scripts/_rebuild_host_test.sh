#!/usr/bin/env bash
# _rebuild_host_test.sh -- recompile + re-run the host chain test (v1 + v2) after the
# second-review runner changes. Run INSIDE WSL (g++ 15.2.0), pure offline, no libiio.
set -euo pipefail

ROOT="/mnt/f/嵌赛/fix10class24_fix1v2_board_impl1_work"
cd "$ROOT"

echo "== compile =="
g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
    -o host_tests/bin/test_radioml_independent_rx \
    host_tests/test_radioml_independent_rx.cpp
echo "BUILD_RC=0"

echo "== v1 =="
rm -rf host_tests/bin/out_v1_rebuild2
host_tests/bin/test_radioml_independent_rx \
  --tx-dir ../fix10class24_independent_rx_delivery_fix1_work/tx_package \
  --reference-tsv ../fix10class24_independent_rx_delivery_fix1_work/replay_out/independent_rx_replay.tsv \
  --reference-layers ../fix10class24_independent_rx_delivery_fix1_work/replay_out/layers \
  --out-dir host_tests/bin/out_v1_rebuild2

echo "== v2 =="
rm -rf host_tests/bin/out_v2_rebuild2
host_tests/bin/test_radioml_independent_rx \
  --tx-dir ../fix10class24_waveform_correct_v2_work/tx_package \
  --reference-tsv ../fix10class24_waveform_correct_v2_work/replay_out/independent_rx_replay.tsv \
  --reference-layers ../fix10class24_waveform_correct_v2_work/replay_out/layers \
  --out-dir host_tests/bin/out_v2_rebuild2
