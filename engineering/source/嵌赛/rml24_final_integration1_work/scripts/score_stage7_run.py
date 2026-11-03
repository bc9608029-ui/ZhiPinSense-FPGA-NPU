#!/usr/bin/env python3
"""Score one final candidate-only board run on the fixed full denominator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def score(expected_path: Path, results_path: Path) -> dict[str, Any]:
    expected_rows = load(expected_path).get("records", [])
    result_rows = load(results_path).get("records", [])
    truth = {int(row["seq"]): row for row in expected_rows}
    results = {int(row["seq"]): row for row in result_rows}
    if len(expected_rows) != 240 or len(truth) != 240:
        raise ValueError("expected truth must contain 240 unique sequences")
    if len(results) != len(result_rows):
        raise ValueError("duplicate sequence in board results")

    matrix = [[0 for _ in range(24)] for _ in range(24)]
    failures = [0 for _ in range(24)]
    missing = []
    correct = 0
    for seq, target in truth.items():
        class_index = int(target["class_index"])
        row = results.get(seq)
        if row is None:
            missing.append(seq)
            failures[class_index] += 1
            continue
        arm = row.get("arms", {}).get("candidate", {})
        pred = arm.get("pred", -1)
        if arm.get("error") or not isinstance(pred, int) or not 0 <= pred < 24:
            failures[class_index] += 1
            continue
        matrix[class_index][pred] += 1
        correct += pred == class_index

    per_class = []
    for class_index in range(24):
        total = sum(matrix[class_index]) + failures[class_index]
        per_class.append(
            {
                "class_index": class_index,
                "class_name": next(str(row["class_name"]) for row in expected_rows if int(row["class_index"]) == class_index),
                "correct": matrix[class_index][class_index],
                "total": total,
                "failures": failures[class_index],
                "accuracy": matrix[class_index][class_index] / total,
            }
        )
    return {
        "kind": "RML24_FINAL_STAGE7_SCORE_V1",
        "denominator_policy": "all 240 expected samples; missing/recovery/inference failures are incorrect",
        "correct": correct,
        "total": 240,
        "accuracy": correct / 240,
        "missing_sequences": sorted(missing),
        "failure_count": sum(failures),
        "per_class": per_class,
        "confusion_matrix": matrix,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = score(args.expected, args.results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "RML24_FINAL_STAGE7_SCORE result=PASS "
        f"correct={summary['correct']} total=240 accuracy={summary['accuracy']:.6f} "
        f"failures={summary['failure_count']} missing={len(summary['missing_sequences'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
