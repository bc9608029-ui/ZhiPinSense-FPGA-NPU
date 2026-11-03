#!/usr/bin/env bash
# Host (WSL/Linux) build of the twelve-class chain host tests.
# iCraft-free and libiio-free: exercises the exact chain_common.hpp / ui_report.hpp
# code the board runs, plus the stream resampler (resampler.cpp).
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter"

mkdir -p bin

echo "== build test_chain_common =="
$CXX $FLAGS test_chain_common.cpp ../sdr_adapter/resampler.cpp -o bin/test_chain_common

echo "== build test_result_frame_v2 =="
$CXX $FLAGS test_result_frame_v2.cpp -o bin/test_result_frame_v2

echo "== build test_restore_semantics =="
$CXX $FLAGS test_restore_semantics.cpp -o bin/test_restore_semantics

echo "== build test_contiguous_cli =="
$CXX $FLAGS test_contiguous_cli.cpp ../sdr_adapter/resampler.cpp -o bin/test_contiguous_cli

echo "== build test_npu_rearm =="
$CXX $FLAGS test_npu_rearm.cpp -o bin/test_npu_rearm

echo "build_host_tests.sh: OK -> host_tests/bin/{test_chain_common,test_result_frame_v2,test_restore_semantics,test_contiguous_cli,test_npu_rearm}"
