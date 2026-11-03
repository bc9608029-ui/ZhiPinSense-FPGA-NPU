#!/usr/bin/env bash
# Run the M23 P0 offline module tests (standalone; independent of run_tests.sh).
set -euo pipefail
cd "$(dirname "$0")"

./bin/test_m23_p0
echo "run_m23_p0.sh: OK"
