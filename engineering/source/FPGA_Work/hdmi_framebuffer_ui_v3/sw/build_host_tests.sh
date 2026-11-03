#!/usr/bin/env bash
# build_host_tests.sh — build & run ALL host-side verification (x86/WSL, no board).
#
# This is the evidence for "which tests were actually run on the host".  It:
#   1. compiles the two unit-test binaries with -Wall -Wextra -O2 (zero warnings),
#   2. runs them (must exit 0),
#   3. rebuilds them under AddressSanitizer + UBSan and re-runs,
#   4. generates the 1280x720 + 1024x600 screenshots and prints pixel hashes.
#
# Requires: g++ (C++17).  ASan/UBSan need a clang/gcc that supports -fsanitize.
#
#   ./build_host_tests.sh

set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
STD="-std=gnu++17 -Wall -Wextra -O2"

BACKEND="direct_framebuffer_backend.cpp"
UI="font.cpp ui_renderer.cpp model_contract.cpp touch.cpp"
IMG="image_writer.cpp"

echo "=== [1/4] build + run: test_direct_framebuffer_backend ==="
$CXX $STD test_direct_framebuffer_backend.cpp $BACKEND -o /tmp/test_dfb
/tmp/test_dfb

echo
echo "=== [2/4] build + run: test_ui ==="
$CXX $STD test_ui.cpp $UI -o /tmp/test_ui
/tmp/test_ui

echo
echo "=== [3/4] build + run under ASan + UBSan ==="
SAN="-fsanitize=address,undefined -fno-omit-frame-pointer -g"
$CXX $STD $SAN test_direct_framebuffer_backend.cpp $BACKEND -o /tmp/test_dfb_asan
ASAN_OPTIONS=detect_leaks=1 /tmp/test_dfb_asan
$CXX $STD $SAN test_ui.cpp $UI -o /tmp/test_ui_asan
ASAN_OPTIONS=detect_leaks=1 /tmp/test_ui_asan

echo
echo "=== [4/4] generate screenshots (1280x720 + 1024x600 + hashes) ==="
$CXX $STD render_screenshots.cpp $UI $IMG -o /tmp/render_screenshots
/tmp/render_screenshots screenshots

echo
echo "ALL HOST TESTS PASSED"
