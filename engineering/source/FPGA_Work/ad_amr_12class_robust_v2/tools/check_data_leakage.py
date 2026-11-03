#!/usr/bin/env python3
"""Check the 12-class real-RF dataset for cross-split leakage.

Checks:
  1. no session_id appears in more than one split (fatal);
  2. no (label, seed) pair straddles the development / final_holdout boundary
     (warning — a same-class same-seed pair across splits may be the same
     underlying waveform);
  3. no golden deployment input (by data SHA-256) is present in the
     development split (fatal — golden inputs must never enter training).

Fail-closed: fatal conditions return non-zero.

Usage:
    python3 tools/check_data_leakage.py --manifest manifest.json --splits splits.json
                                        [--golden golden_manifest.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check real-RF dataset for leakage.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--splits", required=True)
    parser.add_argument("--golden", default=None,
                        help="Golden deployment manifest (or file of data SHA-256, one per line)")
    args = parser.parse_args(argv)

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    splits = json.loads(Path(args.splits).read_text(encoding="utf-8"))

    session_to_split: dict[str, str] = {}
    for session_id, value in splits.get("sessions", {}).items():
        session_to_split[str(session_id)] = value.get("split", "")

    files = manifest.get("files", [])
    if not files:
        print("FAIL: manifest has no files", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    # 1. session -> split consistency.
    session_observed: dict[str, str] = {}
    for entry in files:
        session_id = str(entry.get("session_id", ""))
        split = session_to_split.get(session_id)
        if split is None:
            errors.append(f"record {entry.get('relpath')} has session {session_id!r} not in splits")
            continue
        if session_id in session_observed and session_observed[session_id] != split:
            errors.append(f"session {session_id!r} mapped to multiple splits")
        session_observed[session_id] = split

    # 2. (label, seed) straddle detection.
    label_seed_splits: dict[tuple[str, str], set[str]] = {}
    for entry in files:
        session_id = str(entry.get("session_id", ""))
        split = session_observed.get(session_id, "unknown")
        key = (str(entry.get("label", "")).upper(), str(entry.get("seed", "")))
        label_seed_splits.setdefault(key, set()).add(split)
    for (label, seed), seen_splits in sorted(label_seed_splits.items()):
        if len(seen_splits) > 1:
            warnings.append(
                f"(label={label}, seed={seed}) spans splits {sorted(seen_splits)}"
            )

    # 3. golden inputs must not be in development split.
    if args.golden:
        golden_sha = _load_golden_sha(args.golden)
        for entry in files:
            if session_observed.get(str(entry.get("session_id", "")), "") == "development":
                if entry.get("data_sha256") in golden_sha:
                    errors.append(
                        f"golden input present in development split: {entry.get('relpath')}"
                    )

    if warnings:
        print("WARNINGS:")
        for message in warnings:
            print(f"  {message}")

    if errors:
        print("LEAK FAIL:")
        for message in errors:
            print(f"  {message}")
        return 1

    print("OK: no cross-split leakage detected")
    return 0


def _load_golden_sha(path: str) -> set[str]:
    source = Path(path)
    text = source.read_text(encoding="utf-8").strip()
    result: set[str] = set()
    if text.lstrip().startswith("{"):
        payload = json.loads(text)
        for entry in payload.get("files", []):
            if entry.get("data_sha256"):
                result.add(entry["data_sha256"])
    else:
        for line in text.splitlines():
            value = line.strip()
            if value:
                result.add(value)
    return result


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
