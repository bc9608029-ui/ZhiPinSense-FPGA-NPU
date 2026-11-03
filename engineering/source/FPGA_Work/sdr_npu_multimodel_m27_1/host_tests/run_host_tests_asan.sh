#!/usr/bin/env bash
# AddressSanitizer build + run (offline, WSL g++).  Mirrors M24/M25 asan flags.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
g++ -std=gnu++17 -O1 -g -fsanitize=address -fno-omit-frame-pointer -I../probes \
    test_m27_1_metrics.cpp -o build/test_m27_1_metrics_asan
./build/test_m27_1_metrics_asan
