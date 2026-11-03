#!/usr/bin/env bash
# M29 Phase F4 — build the RML23 merge post-processor ON THE BOARD (aarch64).
#
# The board package ships NO prebuilt binary.  This script compiles the merge
# post-processor and the host self-test from source on the target, then runs the
# self-test against the shipped cross-language reference data.  It refuses to run
# if the host is not an aarch64 (ARM A53) target, so an x86/WSL build can never
# be mistaken for a board binary.
#
#   ./scripts/build_board.sh            # build + self-test
#   CXX=/opt/toolchain/bin/aarch64-linux-g++ ./scripts/build_board.sh   # cross
#
# Output: bin/rml23_merged_main, bin/rml23_merged_test
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

CXX="${CXX:-g++}"
CXXFLAGS="${CXXFLAGS:--std=gnu++17 -O2 -Wall -Wextra -Werror}"

arch="$(uname -m 2>/dev/null || echo unknown)"
case "$arch" in
  aarch64|arm64)
    echo "[build_board] target arch = $arch (ARM A53 OK)"
    ;;
  *)
    # Allow an explicit cross-toolchain to override the host-arch guard; a bare
    # x86 g++ here would produce a binary the board cannot run.
    if [ "${CXX:-g++}" = "g++" ]; then
      echo "FAIL: board build requires an aarch64 toolchain (host arch = $arch)" >&2
      echo "      set CXX=<aarch64-linux-g++> to cross-compile." >&2
      exit 1
    fi
    echo "[build_board] cross-compiling with CXX=$CXX (host arch = $arch)"
    ;;
esac

mkdir -p bin

echo "[build_board] compiling merge post-processor ..."
"$CXX" $CXXFLAGS -I. src/rml23_merged_main.cpp -o bin/rml23_merged_main

echo "[build_board] compiling self-test ..."
"$CXX" $CXXFLAGS -I. rml23_merged_test.cpp -o bin/rml23_merged_test

echo "[build_board] running self-test against shipped reference data ..."
bin/rml23_merged_test test_data

echo "== BOARD BUILD + SELF-TEST PASSED =="
