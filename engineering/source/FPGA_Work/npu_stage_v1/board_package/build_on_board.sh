#!/usr/bin/env bash
# Board-side build of the NPU-only smoke + diagnostic programs.
# Run this ON the FMQL30TAI Linux image (aarch64) after the bitstream is confirmed.
# The on-chip iCraft 3.39 package must provide /usr/cmake/icraft-zg330backend*.cmake
# and /usr/cmake/icraft-hostbackend*.cmake. Both binaries are built with
# -std=gnu++17 and linked against Icraft::ZG330Backend + Icraft::HostBackend.
# Any build failure stops the script immediately (set -e).
set -euo pipefail

cd "$(dirname "$0")"

rm -rf build && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)" npu_only_smoke npu_diag

echo "Built: $(pwd)/npu_only_smoke"
echo "Built: $(pwd)/npu_diag"
