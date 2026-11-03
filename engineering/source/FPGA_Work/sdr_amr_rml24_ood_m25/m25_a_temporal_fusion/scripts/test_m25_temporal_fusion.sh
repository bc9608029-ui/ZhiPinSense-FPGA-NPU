#!/usr/bin/env bash
# test_m25_temporal_fusion.sh -- M25-A one-shot offline verification.
#
# Runs, in order: release host tests, ASan, UBSan, the replay demo, the
# performance benchmark, and a bash syntax check on every .sh file.  Each suite
# exits non-zero on any failed assertion, so a clean run ends with
# TEST_M25_TEMPORAL_FUSION_OK.  Never touches the board / Gate 9/10.
set -euo pipefail
cd "$(dirname "$0")/.."   # project root: m25_a_temporal_fusion

echo "== M25-A host tests: release =="
./host_tests/run_m25_a.sh

echo "== M25-A host tests: ASan =="
./host_tests/run_m25_a_asan.sh

echo "== M25-A host tests: UBSan =="
./host_tests/run_m25_a_ubsan.sh

echo "== M25-A replay: demo =="
./host_tools/build_m25_temporal_fusion_replay.sh
./build/m25/m25_temporal_fusion_replay --demo

echo "== M25-A benchmark =="
./host_tools/build_m25_temporal_fusion_bench.sh
./build/m25/m25_temporal_fusion_bench

echo "== M25-A shell syntax check =="
while IFS= read -r -d '' f; do
  bash -n "$f"
  echo "  ok: $f"
done < <(find . -name '*.sh' -print0)

echo "TEST_M25_TEMPORAL_FUSION_OK"
