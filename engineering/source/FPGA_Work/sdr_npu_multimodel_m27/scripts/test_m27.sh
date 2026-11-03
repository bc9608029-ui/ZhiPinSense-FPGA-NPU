#!/usr/bin/env bash
# M27 offline verification suite.
#   bash -n on every .sh, C++ release + ASan + UBSan (WSL), pytest (channel +
#   expert), channel audits, python -m compileall on every .py.
# Exits non-zero on the first failure.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

echo "== [1/6] bash -n on all scripts =="
while IFS= read -r -d '' f; do
  bash -n "$f"
done < <(find . -name '*.sh' -print0)
echo "    bash -n OK"

echo "== [2/6] C++ release + ASan + UBSan (WSL) =="
bash scripts/run_m27.sh
bash scripts/run_m27_asan.sh
bash scripts/run_m27_ubsan.sh

echo "== [3/6] pytest (channel + expert) =="
python -m pytest channel_proto/tests expert/tests -q

echo "== [4/6] channel audits =="
python channel_proto/m27_channel_isolation_audit.py
python channel_proto/m27_channel_shortcut_audit.py

echo "== [5/6] python -m compileall on all .py =="
python -m compileall -q channel_proto expert
echo "    compileall OK"

echo "== [6/6] done =="
echo "== M27_OFFLINE_VERIFICATION_OK =="
