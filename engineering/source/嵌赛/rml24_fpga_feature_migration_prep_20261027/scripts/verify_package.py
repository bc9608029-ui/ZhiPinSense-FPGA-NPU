#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
required = [
    "rtl/qam_feature_pipeline.sv", "rtl/frame_statistics.sv",
    "rtl/mandatory_core_path.sv", "reference/feature_contract.py",
    "contract/feature_migration_contract.json", "integration/backend_contract.json",
    "evidence/iq_input.hex", "evidence/expected_core.csv", "evidence/manifest.json",
    "docs/BOARDTEST.md", "docs/ROLLBACK.md"
]
missing=[p for p in required if not (ROOT/p).is_file()]
if missing:
    raise SystemExit("MISSING="+",".join(missing))
contract=json.loads((ROOT/"contract/feature_migration_contract.json").read_text(encoding="utf-8"))
assert contract["frame_length"] == 1024
assert contract["per_frame"]["rms"].startswith("software:")
p=subprocess.run([sys.executable, str(ROOT/"scripts/test_contract.py")], capture_output=True, text=True)
if p.returncode:
    print(p.stdout); print(p.stderr, file=sys.stderr); raise SystemExit(p.returncode)
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in required}
print(p.stdout.strip())
print(json.dumps({"result":"PASS","required_files":len(required),"sha256":hashes}, indent=2))
