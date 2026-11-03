#!/usr/bin/env bash
# Offline host build of the M27.1 SDK-free unit tests (no iCraft SDK needed).
# Run under WSL (g++).  Mirrors the M24/M25 release flags.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
g++ -std=gnu++17 -O2 -Wall -Wextra -Werror -I../probes \
    test_m27_1_metrics.cpp -o build/test_m27_1_metrics
echo "Built: $(pwd)/build/test_m27_1_metrics"
