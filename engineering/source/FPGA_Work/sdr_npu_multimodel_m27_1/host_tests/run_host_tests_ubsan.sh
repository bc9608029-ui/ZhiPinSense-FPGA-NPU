#!/usr/bin/env bash
# UndefinedBehaviorSanitizer build + run (offline, WSL g++).  Mirrors M24/M25 ubsan flags.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
g++ -std=gnu++17 -O1 -g -fsanitize=undefined -fno-omit-frame-pointer -I../probes \
    test_m27_1_metrics.cpp -o build/test_m27_1_metrics_ubsan
./build/test_m27_1_metrics_ubsan
