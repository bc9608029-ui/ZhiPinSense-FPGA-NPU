#!/usr/bin/env python3
"""Assign real-RF records to splits by capture session (anti-leakage).

Every record from the same SigMF ``session_id`` must land in the same split.
Sessions are deterministically partitioned into ``development`` and
``final_holdout``; ``final_holdout`` is evaluated exactly once after the
candidate is frozen.

Fail-closed: any record without a session_id, or a session that would straddle
splits, aborts with a non-zero exit.

Usage:
    python3 tools/split_by_session.py --manifest manifest.json --out splits.json
                                      [--holdout-ratio 0.2] [--seed 2026]
                                      [--holdout-sessions FILE]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SPLITS = ("development", "final_holdout")


def session_split_hash(seed: int, session_id: str) -> str:
    return hashlib.sha256(f"{seed}:{session_id}".encode("utf-8")).hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Split real-RF records by session.")
    parser.add_argument("--manifest", required=True, help="Manifest JSON from build_sigmf_manifest.py")
    parser.add_argument("--out", required=True, help="Output splits.json")
    parser.add_argument("--holdout-ratio", type=float, default=0.2,
                        help="Fraction of sessions to hold out (0 < r < 1)")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--holdout-sessions", default=None,
                        help="Optional file listing explicit final_holdout session ids (one per line)")
    args = parser.parse_args(argv)

    if not 0.0 < args.holdout_ratio < 1.0:
        print("FAIL: --holdout-ratio must be in (0, 1)", file=sys.stderr)
        return 2

    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        print(f"FAIL: manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    explicit_holdout: set[str] = set()
    if args.holdout_sessions:
        holdout_path = Path(args.holdout_sessions)
        if not holdout_path.is_file():
            print(f"FAIL: --holdout-sessions not found: {holdout_path}", file=sys.stderr)
            return 2
        for line in holdout_path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value:
                explicit_holdout.add(value)

    files = manifest.get("files", [])
    if not files:
        print("FAIL: manifest has no files", file=sys.stderr)
        return 2

    session_files: dict[str, list[str]] = {}
    for entry in files:
        session_id = entry.get("session_id")
        relpath = entry.get("relpath")
        if not session_id:
            print(f"FAIL: record missing session_id: {relpath}", file=sys.stderr)
            return 2
        if not relpath:
            print("FAIL: record missing relpath", file=sys.stderr)
            return 2
        session_files.setdefault(str(session_id), []).append(relpath)

    # Deterministic holdout selection.
    if explicit_holdout:
        missing_explicit = [s for s in explicit_holdout if s not in session_files]
        if missing_explicit:
            print(f"FAIL: explicit holdout sessions not in manifest: {missing_explicit}",
                  file=sys.stderr)
            return 2
        holdout_sessions = explicit_holdout
    else:
        ordered = sorted(session_files.keys())
        ordered.sort(key=lambda s: session_split_hash(args.seed, s))
        holdout_count = max(1, round(len(ordered) * args.holdout_ratio))
        holdout_sessions = set(ordered[:holdout_count])

    splits: dict[str, dict] = {}
    for session_id, relpaths in session_files.items():
        split = "final_holdout" if session_id in holdout_sessions else "development"
        splits[session_id] = {"split": split, "files": sorted(relpaths)}

    output = {
        "schema_version": 1,
        "holdout_ratio": args.holdout_ratio,
        "seed": args.seed,
        "sessions": splits,
    }
    out_path = Path(args.out)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    n_dev = sum(1 for value in splits.values() if value["split"] == "development")
    n_hold = sum(1 for value in splits.values() if value["split"] == "final_holdout")
    print(f"OK: wrote {out_path}")
    print(f"  sessions={len(splits)} development={n_dev} final_holdout={n_hold}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
