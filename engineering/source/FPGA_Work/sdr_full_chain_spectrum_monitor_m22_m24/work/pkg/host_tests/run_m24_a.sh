#!/usr/bin/env bash
# run_m24_a.sh -- run the M24-A host test (release build).
set -euo pipefail
cd "$(dirname "$0")"

../build/m24/test_m24_a
