#!/usr/bin/env python3
"""Strip private labels from the frozen validation manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.expected.read_text(encoding="utf-8"))
    rows = [
        {"seq": int(row["seq"]), "file": str(row["file"]), "source_sha256": str(row["source_sha256"])}
        for row in source["records"]
    ]
    if len(rows) != 240 or len({row["seq"] for row in rows}) != 240:
        raise SystemExit("expected exactly 240 unique rows")
    result = {
        "kind": "RML24_FINAL_PUBLIC_TX_MANIFEST_V1",
        "contains_labels": False,
        "records": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"RML24_FINAL_PUBLIC_MANIFEST result=PASS rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
