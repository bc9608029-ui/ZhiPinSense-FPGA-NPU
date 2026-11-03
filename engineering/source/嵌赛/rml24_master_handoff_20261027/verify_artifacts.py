#!/usr/bin/env python3
from pathlib import Path
import hashlib, json

root = Path(__file__).resolve().parents[1]
manifest = json.loads((Path(__file__).with_name("ARTIFACTS.json")).read_text(encoding="utf-8"))
for item in manifest["artifacts"]:
    path = root / item["name"]
    if not path.is_file():
        raise SystemExit(f"MISSING {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item["sha256"]:
        raise SystemExit(f"SHA_MISMATCH {item['name']} {actual}")
    print(f"OK {item['name']}")
print("MASTER_HANDOFF_VERIFY result=PASS artifacts=4")
