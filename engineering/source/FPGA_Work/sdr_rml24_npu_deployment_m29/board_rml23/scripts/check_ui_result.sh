#!/usr/bin/env bash
# M29 Phase F4 — validate the RML23-AMSSB-MERGED result log (UI/result check).
#
#   ./scripts/check_ui_result.sh <result.jsonl> <n_frames>
#
# Every result line must be valid JSON and carry the mandatory fields with the
# frozen deployment semantics:
#   - deployment_mode == "AMSSB_MERGED"
#   - expert_enabled  == false, expert_result == "NOT_RUN"   (no fake expert)
#   - merged_23_top1  in [0,22], raw_24_top1 in [0,23]
#   - merged_23_label never "AM-SSB-SC" / "AM-SSB-WC" (only "AM-SSB")
#
# Exit 0 only if every one of the n_frames lines is valid and the field
# constraints hold; otherwise exit 1 with the offending line printed.
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <result.jsonl> <n_frames>" >&2
  exit 2
fi

RESULT="$1"
N_FRAMES="$2"

if [ ! -f "$RESULT" ]; then
  echo "FAIL: result log not found: $RESULT" >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else echo "FAIL: no python3 interpreter" >&2; exit 1; fi

"$PY" - "$RESULT" "$N_FRAMES" <<'PY'
import json, sys
path, expected = sys.argv[1], int(sys.argv[2])
required = {"deployment_mode", "expert_enabled", "expert_result",
            "raw_24_top1", "merged_23_top1", "merged_23_label"}
seen = 0
errors = 0
with open(path, "r", encoding="utf-8") as f:
    for lineno, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"line {lineno}: invalid JSON: {e}", file=sys.stderr); errors += 1; continue
        missing = required - set(rec)
        if missing:
            print(f"line {lineno}: missing fields {sorted(missing)}", file=sys.stderr); errors += 1; continue
        if rec["deployment_mode"] != "AMSSB_MERGED":
            print(f"line {lineno}: deployment_mode={rec['deployment_mode']!r}", file=sys.stderr); errors += 1
        if rec["expert_enabled"] is not False or rec["expert_result"] != "NOT_RUN":
            print(f"line {lineno}: expert must be disabled/NOT_RUN, got "
                  f"enabled={rec['expert_enabled']!r} result={rec['expert_result']!r}", file=sys.stderr); errors += 1
        if not (0 <= rec["raw_24_top1"] <= 23):
            print(f"line {lineno}: raw_24_top1 out of range {rec['raw_24_top1']!r}", file=sys.stderr); errors += 1
        if not (0 <= rec["merged_23_top1"] <= 22):
            print(f"line {lineno}: merged_23_top1 out of range {rec['merged_23_top1']!r}", file=sys.stderr); errors += 1
        lbl = rec["merged_23_label"]
        if lbl in ("AM-SSB-SC", "AM-SSB-WC"):
            print(f"line {lineno}: merged label must be 'AM-SSB', got {lbl!r}", file=sys.stderr); errors += 1
        seen += 1

if seen != expected:
    print(f"FAIL: expected {expected} frames, saw {seen}", file=sys.stderr); errors += 1
if errors:
    print(f"== UI/RESULT CHECK FAILED ({errors} error(s)) ==", file=sys.stderr)
    sys.exit(1)
print(f"== UI/RESULT CHECK PASSED ({seen} frames) ==")
PY
