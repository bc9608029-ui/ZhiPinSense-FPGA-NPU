#!/usr/bin/env bash
# run_m25_a.sh -- build + run the M25-A host test (release).
set -euo pipefail
cd "$(dirname "$0")"

./build_m25_a.sh
../build/m25/test_m25_a

echo "M25_A_OK"
