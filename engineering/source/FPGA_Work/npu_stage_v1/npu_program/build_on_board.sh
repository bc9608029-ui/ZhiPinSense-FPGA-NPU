#!/usr/bin/env bash
# Board-side build of the NPU-only smoke program.
# Run this ON the FMQL30TAI Linux image (aarch64) after the bitstream is confirmed.
# The on-chip iCraft 3.39 package must provide /usr/cmake/icraft-zg330backend*.cmake.
set -euo pipefail

cd "$(dirname "$0")"

rm -rf build && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"

echo "Built: $(pwd)/npu_only_smoke"
