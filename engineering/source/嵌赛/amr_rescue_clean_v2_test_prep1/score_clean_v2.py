"""Fixed-denominator scoring for the generated clean-v2 24-class RF test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board-results", type=Path, required=True)
    ap.add_argument("--expected", type=Path, required=True)
    ap.add_argument("--out-json", type=Path, required=True)
    args = ap.parse_args()
    board_doc = json.loads(args.board_results.read_text(encoding="utf-8"))
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    if len(expected) != 24 or len({x["seq"] for x in expected}) != 24:
        raise RuntimeError("expected_private must contain exactly 24 unique sequences")
    records = board_doc.get("records", [])
    if len({x["seq"] for x in records}) != len(records):
        raise RuntimeError("duplicate board sequence")
    expected_seqs = {int(x["seq"]) for x in expected}
    unexpected = sorted({int(x["seq"]) for x in records} - expected_seqs)
    if unexpected:
        raise RuntimeError(f"unexpected board sequences: {unexpected}")
    got = {int(x["seq"]): x for x in records}
    confusion = [[0] * 24 for _ in range(24)]
    detail = []
    correct = agree_digital = rf_added_errors = board_fixed_digital = failures = 0
    for truth in sorted(expected, key=lambda x: x["seq"]):
        row = got.get(truth["seq"])
        pred = None if row is None else row.get("pred")
        error = "missing" if row is None else row.get("error")
        usable = isinstance(pred, int) and 0 <= pred < 24 and not error
        is_correct = usable and pred == truth["class_index"]
        agrees = usable and pred == truth["digital_pred"]
        correct += int(is_correct)
        agree_digital += int(agrees)
        failures += int(not usable)
        if usable:
            confusion[truth["class_index"]][pred] += 1
        if truth["digital_correct"] and not is_correct:
            rf_added_errors += 1
        if not truth["digital_correct"] and is_correct:
            board_fixed_digital += 1
        detail.append({
            "seq": truth["seq"], "source_index": truth["source_index"],
            "class_index": truth["class_index"], "class_name": truth["class_name"],
            "digital_pred": truth["digital_pred"], "board_pred": pred,
            "board_correct": bool(is_correct), "board_agrees_digital": bool(agrees),
            "error": error,
        })
    complete = len(records) == 24
    verdict = ("CONTINUE" if correct >= 20 else
               ("INVESTIGATE_ONE_DAY" if correct >= 16 else "CLEAN_SIGNAL_TARGET_NOT_MET"))
    if not complete:
        verdict = "INCOMPLETE_MEASUREMENT"
    report = {
        "result": "MEASUREMENT_COMPLETE" if complete else "INCOMPLETE",
        "verdict": verdict,
        "correct": correct,
        "total_fixed_denominator": 24,
        "accuracy": correct / 24,
        "digital_baseline_correct": 23,
        "board_agrees_with_digital_baseline": agree_digital,
        "receiver_failures_or_missing": failures,
        "rf_added_errors_from_digitally_correct_sources": rf_added_errors,
        "board_fixed_known_digital_error": board_fixed_digital,
        "confusion_matrix": confusion,
        "records": detail,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("confusion_matrix", "records")}, indent=2, ensure_ascii=False))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
