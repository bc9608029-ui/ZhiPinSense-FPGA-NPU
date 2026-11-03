#!/usr/bin/env bash
# Host-side pure-logic test build for latency_diag.hpp.
# Run from WSL with the repo under /mnt/f/FPGA_Work/sdr_preparation_v3_logging_fix.
# No iCraft dependency: this only exercises the statistics / parsing / mapping /
# verdict logic in board_package/latency_diag.hpp.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOARD_PKG="$HERE/../board_package"

CXX="${CXX:-g++}"
STD="-std=c++17 -O2 -Wall -Wextra -Werror"

# 1) plain build + run
"$CXX" $STD -I"$BOARD_PKG" "$HERE/test_latency_diag.cpp" -o "$HERE/test_latency_diag"
echo "== plain run =="
"$HERE/test_latency_diag"

# 2) ASan + UBSan build + run
"$CXX" $STD -fsanitize=address,undefined -fno-omit-frame-pointer \
    -I"$BOARD_PKG" "$HERE/test_latency_diag.cpp" -o "$HERE/test_latency_diag_san"
echo "== ASan/UBSan run =="
ASAN_OPTIONS=detect_leaks=1 "$HERE/test_latency_diag_san"

# Clean up the two host-only binaries so they never leak into the package.
rm -f "$HERE/test_latency_diag" "$HERE/test_latency_diag_san"

echo "ALL HOST TESTS PASSED"
