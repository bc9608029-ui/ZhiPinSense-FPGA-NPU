#!/usr/bin/env python3
"""Replay copied board raw captures through the byte-frozen candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "recovery"))
from receiver_core import recover_frame  # noqa: E402
import candidate_two_dc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--board-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=240)
    args = parser.parse_args()

    board = json.loads(args.board_results.read_text(encoding="utf-8-sig"))
    records = board.get("records", [])
    if len(records) != args.expected_count:
        raise SystemExit(f"board result count {len(records)} != {args.expected_count}")

    rows = []
    for row in records:
        seq = int(row["seq"])
        raw_path = args.capture_dir / f"{seq:04d}.raw.npy"
        if not raw_path.is_file():
            rows.append({"seq": seq, "status": "MISSING_RAW"})
            continue
        try:
            raw = np.load(raw_path, allow_pickle=False)
            frame = recover_frame(raw, candidate_two_dc.recover)
            expected_sha = row["arms"]["candidate"]["input_sha256"]
            rows.append(
                {
                    "seq": seq,
                    "status": "MATCH" if frame.tensor_sha256 == expected_sha else "SHA_MISMATCH",
                    "expected_sha256": expected_sha,
                    "actual_sha256": frame.tensor_sha256,
                    "metadata": frame.metadata,
                }
            )
        except Exception as exc:
            rows.append({"seq": seq, "status": "RECOVERY_ERROR", "error": f"{type(exc).__name__}: {exc}"})

    matched = sum(row["status"] == "MATCH" for row in rows)
    report = {
        "token": "RML24_FINAL_RAW_REPLAY_V1",
        "status": "PASS" if matched == args.expected_count else "FAIL",
        "matched": matched,
        "expected": args.expected_count,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

