#!/usr/bin/env bash
# Fix4 REVIEW-R1 host-test runner (offline, no board/SDR/train).  Runs the
# corrected host tests and fails the suite if any single test fails.
#
# Run:  bash host_tests/run_tests_r1.sh
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT" || exit 2

TESTS=(
  test_fix4_r1_reference_means.py
  test_fix4_r1_no_leak.py
  test_fix4_r1_digital_noop.py
  test_trackers_smoke.py
  test_reestimate_failclosed.py
  test_m0_byterepro.py
)

RC=0
for t in "${TESTS[@]}"; do
  echo "=== $t ==="
  if ! python -I "host_tests/$t"; then
    echo "FAILED: $t"
    RC=1
  fi
done

echo
if [ "$RC" -eq 0 ]; then
  echo "ALL REVIEW-R1 HOST TESTS PASS"
else
  echo "REVIEW-R1 HOST TEST SUITE FAILED"
fi
exit "$RC"
