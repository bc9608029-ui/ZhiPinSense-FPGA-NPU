#!/usr/bin/env bash
# Fix4 host-test runner (offline, no board/SDR/train).  Runs every host test and
# fails the whole suite if any single test fails.
#
# Run:  bash host_tests/run_tests.sh
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT" || exit 2

TESTS=(
  test_trackers_smoke.py
  test_trackers_no_leak.py
  test_digital_clean_noop.py
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
  echo "ALL HOST TESTS PASS"
else
  echo "HOST TEST SUITE FAILED"
fi
exit "$RC"
