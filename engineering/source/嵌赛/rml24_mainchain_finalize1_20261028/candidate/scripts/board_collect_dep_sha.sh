#!/usr/bin/env bash
# Board-side collection of the 4 BASE-sourced runtime deps' SHA256.
# COLLECTION ONLY: prints measured values; it NEVER auto-accepts or writes a
# frozen manifest.  A human must compare the output against the documented
# expected values in docs/DEPENDENCY_IDENTITY.md before feeding an --expect
# manifest back into scripts/preflight_deploy.py.
#
# usage: bash board_collect_dep_sha.sh --base BASE [--test TEST_TREE]
set -euo pipefail

BASE=""; TEST=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    --test) TEST="$2"; shift 2 ;;
    *) echo "usage: $0 --base BASE [--test TEST_TREE]" >&2; exit 2 ;;
  esac
done
[ -n "$BASE" ] || { echo "usage: $0 --base BASE [--test TEST_TREE]" >&2; exit 2; }

RELS=(
  rml24_final/runtime/standalone_control.py
  rml24_final/runtime/radio_tuning.py
  rml24_final/runtime/scan_runtime.py
  rml24_final/board_runtime/rml24_dualmode_receiver_centered_v2.py
)

echo "=== BASE ($BASE) ==="
for r in "${RELS[@]}"; do
  f="$BASE/$r"
  if [ -f "$f" ]; then sha256sum "$f"; else echo "MISSING  $f" >&2; fi
done

if [ -n "$TEST" ]; then
  echo "=== TEST ($TEST) ==="
  for r in "${RELS[@]}"; do
    f="$TEST/$r"
    if [ -f "$f" ]; then sha256sum "$f"; else echo "MISSING  $f" >&2; fi
  done
fi

cat <<'EOF'
=== EXPECTED (docs/DEPENDENCY_IDENTITY.md, for human comparison only) ===
standalone_control.py              522aeaaa10d5a7e0472478a088ab04c38855876fcbf4eeb0592800cc52de6799  (循环复制证据，身份最弱)
radio_tuning.py                    a6df471b9d69f37334546b436d32eb3aff3f9ea8012027aafd9738c981a323bf  (10-27 独立)
scan_runtime.py                    26d38b8eddbaf299a2e396198e392b3e6e3f618bc97290aeb836f07331ed7a9b  (10-27 独立)
rml24_dualmode_receiver_centered_v2.py 11061886abbd51d63eb1ac70bd555d06688e0b673759dc46cb475d2161ef2b36  (10-27 独立)
=== 不符即停止；确认一致后把 BASE 实测结果写成 `sha256  relpath` 清单，再用
===   python3 .../preflight_deploy.py --tree TEST --expect 清单  严格复验。 ===
EOF
