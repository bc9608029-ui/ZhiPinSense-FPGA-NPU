#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
./build_host_tests.sh
./build/test_m27_1_metrics
