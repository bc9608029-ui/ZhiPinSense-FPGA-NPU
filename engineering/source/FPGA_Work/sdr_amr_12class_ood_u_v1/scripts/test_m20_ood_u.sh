#!/usr/bin/env bash
# M20 OOD-U test gate: pytest (19 categories) + C++ build (release + ASan/UBSan).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[test_m20_ood_u] pytest (m20 tests)"
python -m pytest tests/test_m20_*.py -q

echo "[test_m20_ood_u] C++ detector build + unit test (release + ASan/UBSan)"
bash cpp/build_ood_u.sh

echo "[test_m20_ood_u] bash syntax check"
for f in scripts/run_m20_*.sh scripts/test_m20_ood_u.sh cpp/build_ood_u.sh; do
  bash -n "$f"
done

echo "M20_TEST_RESULT result=PASS"
