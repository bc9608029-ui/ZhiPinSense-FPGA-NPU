#!/usr/bin/env bash
# _build_bline.sh -- fix2 B-line host build + sync-invariance verification (run under WSL).
set -e
WORK="/mnt/f/嵌赛/fix10class24_independent_rx_recovery_fix2_work"
CAP="/mnt/f/嵌赛/board_capture/rml24_independent_v2_dual_1773374217_210"
CXX="g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter"

cd "$WORK"
mkdir -p host_tests/bin

echo "== compile test_sync_fft_invariant =="
$CXX -o host_tests/bin/test_sync_fft_invariant host_tests/test_sync_fft_invariant.cpp

echo "== compile test_radioml_independent_rx (header still builds) =="
$CXX -o host_tests/bin/test_radioml_independent_rx host_tests/test_radioml_independent_rx.cpp

echo "== run sync invariance on 24 real captures =="
host_tests/bin/test_sync_fft_invariant "$CAP"
