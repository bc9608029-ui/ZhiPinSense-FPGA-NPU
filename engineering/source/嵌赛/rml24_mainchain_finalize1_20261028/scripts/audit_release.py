#!/usr/bin/env python3
"""Fail-closed offline audit for the main-chain candidate release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_score(name: str) -> dict:
    path = ROOT / "evidence" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if data.get("denominator") != 240 or not isinstance(rows, list) or len(rows) != 240:
        raise RuntimeError(f"{name}: denominator/row count is not 240")
    if sorted(row.get("index", -1) for row in rows) != list(range(240)):
        raise RuntimeError(f"{name}: missing or duplicate sample index")
    correct = sum(row.get("pred") == row.get("label") for row in rows)
    missing = sum(row.get("chosen_frame") is None for row in rows)
    if correct != data.get("correct") or missing != data.get("missing"):
        raise RuntimeError(f"{name}: summary does not match rows")
    return data


def verify_candidate_manifest() -> int:
    base = ROOT / "candidate"
    manifest = base / "SHA256SUMS_UI2.txt"
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split(maxsplit=1)
        relative = relative.lstrip("*")
        path = base / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual.lower() != digest.lower():
            raise RuntimeError(f"candidate checksum mismatch: {relative}")
        checked += 1
    return checked


def main() -> int:
    baseline_fixed = load_score("baseline_fixed.json")
    baseline_scan = load_score("baseline_scan.json")
    candidate_fixed = load_score("candidate_fixed.json")
    candidate_scan = load_score("candidate_scan.json")
    checks = {
        "fixed_no_missing": candidate_fixed["missing"] == 0,
        "scan_no_missing": candidate_scan["missing"] == 0,
        "fixed_not_regressed": candidate_fixed["correct"] >= baseline_fixed["correct"],
        "scan_not_regressed": candidate_scan["correct"] >= baseline_scan["correct"],
        "fixed_gain": candidate_fixed["correct"] - baseline_fixed["correct"],
        "scan_gain": candidate_scan["correct"] - baseline_scan["correct"],
        "candidate_files_checked": verify_candidate_manifest(),
    }
    failed = [key for key, value in checks.items() if isinstance(value, bool) and not value]
    verdict = "PROMOTION_CANDIDATE" if not failed else "DO_NOT_PROMOTE"
    result = {
        "verdict": verdict,
        "checks": checks,
        "scores": {
            "baseline_fixed": baseline_fixed["correct"],
            "candidate_fixed": candidate_fixed["correct"],
            "baseline_scan": baseline_scan["correct"],
            "candidate_scan": candidate_scan["correct"],
            "denominator_each": 240,
        },
        "limits": [
            "decision-only; this script does not install or start services",
            "UI2 has offline tests but still requires target C++ build and physical touch/display acceptance",
            "candidate uses the same existing 240 source identities, not unseen-waveform generalization",
        ],
    }
    out = ROOT / "results" / "release_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"MAINCHAIN_RELEASE_AUDIT verdict={verdict} checks={len(checks)} failed={len(failed)}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
