#!/usr/bin/env bash
# run_24class_oe_shortcut_audit.sh — M25-B generator-shortcut audit over OE records.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python - "${1:-}" <<'PY'
import json
import sys
from audit.m25b_shortcut_audit import audit_shortcut

path = sys.argv[1] or ""
if path:
    with open(path, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    result = audit_shortcut(records)
else:
    # Offline self-check: clean synthetic records (no ID-generator provenance).
    result = audit_shortcut([
        {"modulation": "CW", "source": "far", "family_code": 6, "split_code": 1, "split_name": "ood_validation"},
        {"modulation": "GFSK", "source": "near", "family_code": 1, "split_code": 0, "split_name": "oe_aux_train"},
    ])
print(json.dumps(result, indent=2, sort_keys=True))
if result["status"] != "M25B_SHORTCUT_CLEAN":
    raise SystemExit(1)
PY

echo "M25B_SHORTCUT_AUDIT result=OK"
