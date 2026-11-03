#!/usr/bin/env python3
"""Fixed-denominator multi-signal run scoring (contract sec. 8).

Scores one board/offline run against a frozen expected-target set.  Detection and
classification are reported SEPARATELY, and a missed target is a FIXED error that
is never dropped from the denominator (``detection_rate = detected / expected``).

Inputs
------
--truth FILE            JSON array of expected targets, each with:
                        truth_id, center_hz, class_name, entry_seconds,
                        exit_seconds (use null or +inf for still-active),
                        optional power_db (relative dB, NOT dBm), bw_hz.
--observations FILE     JSONL, one observation per line, each with at least:
                        target_id, center_hz, last_seen (seconds),
                        top3 ([{class_name, confidence}]), confidence.
--out FILE              JSON report destination (default stdout).

Options
-------
--match-radius-hz N     frequency match radius (default 6250 = contract merge radius).
--time-window T0,T1     only score observations with T0 <= last_seen < T1.

Exit codes
----------
0  scored (including runs that legitimately scored 0/0).
1  input malformed (fail-closed: never emit a wrong denominator).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.scoring import GroundTruthTarget, score  # noqa: E402


def _load_truth(path: Path) -> list[GroundTruthTarget]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("--truth must be a JSON array")
    truth: list[GroundTruthTarget] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(f"--truth[{i}] is not an object")
        missing = [k for k in ("truth_id", "center_hz", "class_name",
                               "entry_seconds", "exit_seconds") if k not in item]
        if missing:
            raise SystemExit(f"--truth[{i}] missing fields: {missing}")
        exit_sec = item["exit_seconds"]
        if exit_sec is None:
            exit_sec = math.inf
        truth.append(GroundTruthTarget(
            truth_id=int(item["truth_id"]),
            center_hz=int(item["center_hz"]),
            class_name=str(item["class_name"]),
            entry_seconds=float(item["entry_seconds"]),
            exit_seconds=float(exit_sec),
            power_db=float(item.get("power_db", 0.0)),
            bw_hz=int(item.get("bw_hz", 0)),
        ))
    return truth


def _load_observations(path: Path) -> list[dict]:
    obs: list[dict] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--observations line {lineno}: invalid JSON: {exc}")
        if not isinstance(row, dict):
            raise SystemExit(f"--observations line {lineno}: not an object")
        missing = [k for k in ("target_id", "center_hz", "last_seen") if k not in row]
        if missing:
            raise SystemExit(f"--observations line {lineno} missing fields: {missing}")
        obs.append(row)
    return obs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--truth", required=True, type=Path)
    p.add_argument("--observations", required=True, type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--match-radius-hz", type=int, default=6250)
    p.add_argument("--time-window", type=str, default=None,
                   help="T0,T1 seconds (inclusive left, exclusive right)")
    args = p.parse_args()

    truth = _load_truth(args.truth)
    observations = _load_observations(args.observations)

    window = None
    if args.time_window:
        parts = args.time_window.split(",")
        if len(parts) != 2:
            raise SystemExit("--time-window must be T0,T1")
        try:
            window = (float(parts[0]), float(parts[1]))
        except ValueError:
            raise SystemExit("--time-window values must be numeric")

    report = score(truth, observations,
                   match_radius_hz=args.match_radius_hz, time_window=window)
    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
        print(f"report written to {args.out}")
    else:
        print(payload)

    # Fixed denominator is structural (expected_targets is never edited down).
    if report.expected_targets == 0:
        print("WARNING: zero expected targets; detection_rate is 0.0 by definition")
    print(f"detection={report.detected_targets}/{report.expected_targets} "
          f"rate={report.detection_rate:.4f} "
          f"missed={report.missed_truth_ids} "
          f"false_alarm={report.false_alarm_target_ids} "
          f"class_acc={report.classification.accuracy:.4f} "
          f"({report.classification.correct}/{report.classification.classified})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
