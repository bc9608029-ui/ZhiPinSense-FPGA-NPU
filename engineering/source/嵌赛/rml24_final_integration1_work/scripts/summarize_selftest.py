#!/usr/bin/env python3
"""Summarize frozen paired RF results without changing the test denominator."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ARMS = ("baseline", "candidate")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_prediction(arm: dict[str, Any]) -> int | None:
    prediction = arm.get("pred")
    if arm.get("error") or not isinstance(prediction, int) or not 0 <= prediction < 24:
        return None
    return prediction


def summarize(expected_path: Path, board_paths: list[Path]) -> dict[str, Any]:
    expected_document = load_json(expected_path)
    expected_rows = expected_document.get("records", [])
    if len(expected_rows) != 240:
        raise ValueError(f"expected exactly 240 truth rows, got {len(expected_rows)}")
    truth = {int(row["seq"]): row for row in expected_rows}
    if len(truth) != 240:
        raise ValueError("duplicate seq in expected data")
    class_names = {int(row["class_index"]): str(row["class_name"]) for row in expected_rows}
    if set(class_names) != set(range(24)):
        raise ValueError("expected data does not cover all 24 classes")

    sessions: list[dict[str, Any]] = []
    combined_rows: list[tuple[str, int, dict[str, Any], dict[str, Any]]] = []
    for path in board_paths:
        document = load_json(path)
        rows = document.get("records", [])
        by_seq = {int(row["seq"]): row for row in rows}
        if len(by_seq) != len(rows):
            raise ValueError(f"duplicate seq in {path}")
        if set(by_seq) != set(truth):
            missing = sorted(set(truth) - set(by_seq))
            extra = sorted(set(by_seq) - set(truth))
            raise ValueError(f"incomplete session {path}: missing={missing} extra={extra}")
        session = {"name": path.parent.name, "path": str(path), "total": 240, "arms": {}}
        for arm_name in ARMS:
            correct = 0
            failures = 0
            for seq, target in truth.items():
                arm = by_seq[seq].get("arms", {}).get(arm_name, {})
                prediction = valid_prediction(arm)
                failures += prediction is None
                correct += prediction == int(target["class_index"])
            session["arms"][arm_name] = {
                "correct": correct,
                "failures": failures,
                "accuracy": correct / 240,
            }
        sessions.append(session)
        combined_rows.extend((session["name"], seq, truth[seq], by_seq[seq]) for seq in sorted(truth))

    total = 240 * len(sessions)
    arms: dict[str, Any] = {}
    for arm_name in ARMS:
        matrix = [[0 for _ in range(24)] for _ in range(24)]
        failures = [0 for _ in range(24)]
        correct = 0
        for _, _, target, board_row in combined_rows:
            class_index = int(target["class_index"])
            prediction = valid_prediction(board_row.get("arms", {}).get(arm_name, {}))
            if prediction is None:
                failures[class_index] += 1
            else:
                matrix[class_index][prediction] += 1
                correct += prediction == class_index
        per_class = []
        for class_index in range(24):
            class_total = sum(matrix[class_index]) + failures[class_index]
            per_class.append(
                {
                    "class_index": class_index,
                    "class_name": class_names[class_index],
                    "correct": matrix[class_index][class_index],
                    "total": class_total,
                    "failures": failures[class_index],
                    "accuracy": matrix[class_index][class_index] / class_total,
                }
            )
        arms[arm_name] = {
            "correct": correct,
            "total": total,
            "failures": sum(failures),
            "accuracy": correct / total,
            "per_class": per_class,
            "confusion_matrix": matrix,
        }

    fixes: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    for session_name, seq, target, board_row in combined_rows:
        wanted = int(target["class_index"])
        baseline = valid_prediction(board_row.get("arms", {}).get("baseline", {}))
        candidate = valid_prediction(board_row.get("arms", {}).get("candidate", {}))
        record = {
            "session": session_name,
            "seq": seq,
            "class_index": wanted,
            "class_name": class_names[wanted],
            "baseline_pred": baseline,
            "candidate_pred": candidate,
        }
        if baseline != wanted and candidate == wanted:
            fixes.append(record)
        if baseline == wanted and candidate != wanted:
            regressions.append(record)

    return {
        "kind": "RML24_FINAL_SELFTEST_SUMMARY_V1",
        "denominator_policy": "all expected samples; failures remain incorrect",
        "sessions": sessions,
        "combined": {
            "total": total,
            "arms": arms,
            "fixes": fixes,
            "regressions": regressions,
            "strict_no_regression_gate": len(regressions) == 0,
        },
    }


def write_per_class_tsv(path: Path, summary: dict[str, Any]) -> None:
    rows = []
    for class_index in range(24):
        baseline = summary["combined"]["arms"]["baseline"]["per_class"][class_index]
        candidate = summary["combined"]["arms"]["candidate"]["per_class"][class_index]
        rows.append(
            {
                "class_index": class_index,
                "class_name": candidate["class_name"],
                "total": candidate["total"],
                "baseline_correct": baseline["correct"],
                "baseline_accuracy": f'{baseline["accuracy"]:.6f}',
                "candidate_correct": candidate["correct"],
                "candidate_accuracy": f'{candidate["accuracy"]:.6f}',
                "delta_correct": candidate["correct"] - baseline["correct"],
                "candidate_failures": candidate["failures"],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--board-results", type=Path, action="append", required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-tsv", type=Path, required=True)
    args = parser.parse_args()
    summary = summarize(args.expected, args.board_results)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_per_class_tsv(args.out_tsv, summary)
    combined = summary["combined"]
    print(
        "RML24_FINAL_SELFTEST_SUMMARY result=PASS "
        f'total={combined["total"]} '
        f'baseline={combined["arms"]["baseline"]["correct"]} '
        f'candidate={combined["arms"]["candidate"]["correct"]} '
        f'fixes={len(combined["fixes"])} regressions={len(combined["regressions"])}'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
