#!/usr/bin/env python3
"""Fail-closed audit of the frozen two-round RF evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED = {
    "candidate_two_dc.py": "e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a",
    "generate_validation_sets.py": "c46dff2ac2710cec84c9cff92d776b3caab6a976dff997e29b9538a66ae5bef4",
    "validation_seed5100000/expected_private.json": "67d94d4587100e39a90c0f1589f1d187caea1272a30a3c4bf764f5e6ff8b8a45",
    "development_seed4100000/expected_private.json": "17561cb9a8ebf77174435cfe3d8543097b846e10293908fd1fddfe29c8c025c4",
    "validation_rf_r1/board_results.json": "898882c42e83d51a1f264af890bd288ecf0c480446fa81167ab32060d20b0283",
    "validation_rf_r2/board_results.json": "8a728e14f86b3ede7c0b1ac5a69c8ef8785f0e48c4a913ce6794c410bddbc6d5",
}

ROUND_EXPECTED = {
    "validation_rf_r1": {"baseline": 205, "candidate": 233, "fixes": 28},
    "validation_rf_r2": {"baseline": 198, "candidate": 230, "fixes": 32},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check(condition: bool, name: str, details: Any, checks: list[dict[str, Any]]) -> None:
    checks.append({"name": name, "pass": bool(condition), "details": details})


def recompute(expected_records: list[dict[str, Any]], board: dict[str, Any]) -> dict[str, Any]:
    truth = {int(row["seq"]): row for row in expected_records}
    rows = board.get("records", [])
    got = {int(row["seq"]): row for row in rows}
    if len(got) != len(rows):
        raise ValueError("duplicate sequence in board results")
    result: dict[str, Any] = {"n": len(truth), "received": len(rows), "arms": {}, "fixes": [], "regressions": []}
    for arm in ("baseline", "candidate"):
        correct = failures = 0
        for seq, target in truth.items():
            value = got.get(seq, {}).get("arms", {}).get(arm, {})
            pred = value.get("pred")
            valid = isinstance(pred, int) and 0 <= pred < 24 and "error" not in value
            correct += int(valid and pred == int(target["class_index"]))
            failures += int(not valid)
        result["arms"][arm] = {"correct": correct, "failures": failures}
    for seq, target in truth.items():
        baseline = got.get(seq, {}).get("arms", {}).get("baseline", {}).get("pred")
        candidate = got.get(seq, {}).get("arms", {}).get("candidate", {}).get("pred")
        target_class = int(target["class_index"])
        if baseline != target_class and candidate == target_class:
            result["fixes"].append(seq)
        if baseline == target_class and candidate != target_class:
            result["regressions"].append(seq)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--integration-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    source = args.source_root.resolve()
    integration = args.integration_root.resolve()
    checks: list[dict[str, Any]] = []

    for relative, expected_hash in EXPECTED.items():
        path = source / relative
        actual = sha256(path) if path.is_file() else None
        check(actual == expected_hash, f"sha:{relative}", {"expected": expected_hash, "actual": actual}, checks)

    vendored = integration / "recovery" / "candidate_two_dc.py"
    check(sha256(vendored) == EXPECTED["candidate_two_dc.py"], "vendored_candidate_byte_exact", sha256(vendored), checks)

    sums_ok = sums_total = 0
    for line in (source / "FINAL_SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2 or len(fields[0]) != 64:
            continue
        sums_total += 1
        relative = fields[1].lstrip("*")
        path = source / relative
        sums_ok += int(path.is_file() and sha256(path).lower() == fields[0].lower())
    check(sums_total == 46 and sums_ok == sums_total, "source_final_sha256sums", {"ok": sums_ok, "total": sums_total}, checks)

    validation = load(source / "validation_seed5100000" / "expected_private.json")["records"]
    development = load(source / "development_seed4100000" / "expected_private.json")["records"]
    for name, rows, per_class in (("validation", validation, 10), ("development", development, 5)):
        counts = Counter(int(row["class_index"]) for row in rows)
        hashes = [row["source_sha256"] for row in rows]
        check(len(rows) == 24 * per_class, f"{name}_row_count", len(rows), checks)
        check(counts == Counter({index: per_class for index in range(24)}), f"{name}_class_balance", dict(counts), checks)
        check(len(set(hashes)) == len(hashes), f"{name}_unique_source_hashes", len(set(hashes)), checks)
    dev_hashes = {row["source_sha256"] for row in development}
    val_hashes = {row["source_sha256"] for row in validation}
    check(not (dev_hashes & val_hashes), "development_validation_disjoint", len(dev_hashes & val_hashes), checks)

    round_input_hashes: dict[str, list[str]] = {}
    for round_name, expected_score in ROUND_EXPECTED.items():
        board = load(source / round_name / "board_results.json")
        score = recompute(validation, board)
        check(board.get("receiver_has_labels") is False, f"{round_name}_receiver_label_blind", board.get("receiver_has_labels"), checks)
        check(score["received"] == 240, f"{round_name}_complete", score["received"], checks)
        for arm in ("baseline", "candidate"):
            check(score["arms"][arm]["correct"] == expected_score[arm], f"{round_name}_{arm}_score", score["arms"][arm], checks)
            check(score["arms"][arm]["failures"] == 0, f"{round_name}_{arm}_no_failures", score["arms"][arm], checks)
        check(len(score["fixes"]) == expected_score["fixes"], f"{round_name}_fix_count", len(score["fixes"]), checks)
        check(not score["regressions"], f"{round_name}_no_regressions", score["regressions"], checks)
        restore = load(source / round_name / "restore.json")
        check(restore == [], f"{round_name}_restore_clean", restore, checks)
        round_input_hashes[round_name] = [
            row["arms"]["candidate"]["input_sha256"] for row in board["records"]
        ]

    same_round_inputs = sum(
        left == right
        for left, right in zip(round_input_hashes["validation_rf_r1"], round_input_hashes["validation_rf_r2"])
    )
    check(same_round_inputs == 0, "independent_rf_rounds_have_distinct_recovered_inputs", same_round_inputs, checks)

    if args.model_dir is not None:
        model_dir = args.model_dir.resolve()
        raw_hash = sha256(model_dir / "rml24_adamrv11_bf16.raw")
        json_hash = sha256(model_dir / "rml24_adamrv11_bf16.json")
        check(raw_hash == "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151", "model_raw_sha", raw_hash, checks)
        check(json_hash == "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42", "model_json_sha", json_hash, checks)

    report = {
        "token": "RML24_FINAL_OFFLINE_EVIDENCE_AUDIT_V1",
        "status": "PASS" if all(item["pass"] for item in checks) else "FAIL",
        "checks_passed": sum(item["pass"] for item in checks),
        "checks_total": len(checks),
        "validation_combined": {"baseline": 403, "candidate": 463, "total": 480},
        "raw_capture_replay": "PENDING_CAPTURE_COPY",
        "checks": checks,
    }
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "checks"}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

