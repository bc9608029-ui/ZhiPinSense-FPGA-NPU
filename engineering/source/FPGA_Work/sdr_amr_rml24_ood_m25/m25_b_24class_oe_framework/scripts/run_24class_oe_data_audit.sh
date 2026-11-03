#!/usr/bin/env bash
# run_24class_oe_data_audit.sh — M25-B three-way isolation audit over OE records.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python - "${1:-}" <<'PY'
import json
import sys
from audit.m25b_isolation_audit import audit_isolation

path = sys.argv[1] or ""
if path:
    with open(path, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    result = audit_isolation(records)
else:
    # Offline self-check: two disjoint splits, no collision.
    result = audit_isolation([
        {"modulation": "LFM", "source": "far", "family_code": 5, "split_code": 0, "split_name": "oe_aux_train"},
        {"modulation": "LFM", "source": "far", "family_code": 5, "split_code": 1, "split_name": "ood_validation"},
        {"modulation": "2FSK", "source": "near", "family_code": 0, "split_code": 2, "split_name": "ood_final_test"},
    ])
print(json.dumps(result, indent=2, sort_keys=True))
if result["status"] != "M25B_ISOLATION_OK":
    raise SystemExit(1)
PY

echo "M25B_DATA_AUDIT result=OK"
