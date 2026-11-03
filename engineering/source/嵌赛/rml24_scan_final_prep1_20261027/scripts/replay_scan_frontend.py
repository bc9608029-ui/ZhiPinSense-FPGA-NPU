#!/usr/bin/env python3
"""Replay the scan front-end on saved real-RF captures without NPU inference."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from scan_runtime import detect_public_training, remove_coarse_cfo  # noqa: E402


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("frozen_candidate_two_dc", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load candidate module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.10)
    args = parser.parse_args()

    candidate = load_module(args.candidate)
    paths = sorted(args.captures.rglob("*.raw.npy"))
    if not paths:
        raise RuntimeError("no saved raw captures found")
    rows = []
    for path in paths:
        raw = np.load(path)
        detection = detect_public_training(raw, candidate.train)
        accepted = detection.score >= args.threshold
        recovered = False
        residual_cfo_hz = None
        error = None
        if accepted:
            try:
                corrected = remove_coarse_cfo(raw, detection.coarse_cfo_hz)
                _, metadata = candidate.recover(corrected)
                residual_cfo_hz = float(metadata["cfo_hz"])
                recovered = True
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "path": str(path.relative_to(args.captures)).replace("\\", "/"),
                "public_score": detection.score,
                "coarse_cfo_hz": detection.coarse_cfo_hz,
                "public_start": detection.start,
                "accepted": accepted,
                "two_dc_recovered_after_coarse": recovered,
                "residual_cfo_hz": residual_cfo_hz,
                "error": error,
            }
        )

    summary = {
        "kind": "RML24_SCAN_FRONTEND_REALRF_REPLAY_V1",
        "labels_used": False,
        "threshold": args.threshold,
        "captures": len(rows),
        "accepted": sum(bool(row["accepted"]) for row in rows),
        "two_dc_recovered_after_coarse": sum(bool(row["two_dc_recovered_after_coarse"]) for row in rows),
        "score_min": min(float(row["public_score"]) for row in rows),
        "score_median": float(np.median([float(row["public_score"]) for row in rows])),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        "SCAN_FRONTEND_REPLAY "
        f"captures={summary['captures']} accepted={summary['accepted']} "
        f"two_dc_recovered={summary['two_dc_recovered_after_coarse']} "
        f"score_min={summary['score_min']:.6f} score_median={summary['score_median']:.6f}",
        flush=True,
    )
    return 0 if summary["accepted"] == len(rows) and summary["two_dc_recovered_after_coarse"] == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())

