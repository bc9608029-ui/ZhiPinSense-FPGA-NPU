#!/usr/bin/env python3
"""Evaluate label-blind temporal aggregation on the frozen diagnostic RF run.

This is an offline development-only analysis.  The label is used only after a
candidate prediction has been produced.  Aggregators consume NPU logits and
capture order only; they never consume labels, sample ids, or source IQ.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter
from pathlib import Path


def argmax(values: list[float]) -> int:
    return max(range(len(values)), key=values.__getitem__)


def softmax(values: list[float]) -> list[float]:
    peak = max(values)
    exps = [math.exp(v - peak) for v in values]
    total = sum(exps)
    return [v / total for v in exps]


def mean_vectors(vectors: list[list[float]], weights: list[float] | None = None) -> list[float]:
    if weights is None:
        weights = [1.0] * len(vectors)
    denom = sum(weights)
    return [sum(w * row[i] for row, w in zip(vectors, weights)) / denom for i in range(len(vectors[0]))]


def majority(predictions: list[int]) -> int:
    counts = Counter(predictions)
    # Deterministic tie break: earliest prediction among tied classes.
    best = max(counts.values())
    return next(p for p in predictions if counts[p] == best)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnostic", required=True, type=Path)
    ap.add_argument("--replay", required=True, type=Path)
    ap.add_argument("--events", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    diagnostic = json.loads(args.diagnostic.read_text(encoding="utf-8"))
    with gzip.open(args.replay, "rt", encoding="utf-8") as handle:
        replay = json.load(handle)["results"]
    events = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines() if line.strip()]

    event_by_frame = {
        int(row["frame_id"]): int(row["event_index"])
        for row in diagnostic["rows"]
        if row.get("event_index") is not None
    }
    grouped: dict[int, list[dict]] = {int(event["index"]): [] for event in events}
    for item in replay:
        event_index = event_by_frame.get(int(item["frame_id"]))
        if event_index is not None:
            grouped[event_index].append(item)
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row["frame_id"]))

    methods: dict[str, dict[int, int]] = {}
    for n in (1, 2, 3):
        methods[f"mean_logits_n{n}"] = {}
        methods[f"mean_prob_n{n}"] = {}
        methods[f"confidence_weighted_logits_n{n}"] = {}
        methods[f"majority_n{n}"] = {}
        for event_index, rows in grouped.items():
            selected = rows[:n]
            if len(selected) < n:
                continue
            logits = [list(map(float, row["result"]["mean_logits"])) for row in selected]
            confidences = [max(1e-9, float(row["result"]["confidence"])) for row in selected]
            predictions = [int(row["result"]["pred"]) for row in selected]
            methods[f"mean_logits_n{n}"][event_index] = argmax(mean_vectors(logits))
            methods[f"mean_prob_n{n}"][event_index] = argmax(mean_vectors([softmax(v) for v in logits]))
            methods[f"confidence_weighted_logits_n{n}"][event_index] = argmax(mean_vectors(logits, confidences))
            methods[f"majority_n{n}"][event_index] = majority(predictions)

    event_labels = {int(event["index"]): int(event["label"]) for event in events}
    summary = {}
    details = {}
    for name, predictions in methods.items():
        correct = sum(pred == event_labels[index] for index, pred in predictions.items())
        missing = len(events) - len(predictions)
        summary[name] = {
            "correct": correct,
            "denominator": len(events),
            "accuracy": correct / len(events),
            "available": len(predictions),
            "missing": missing,
        }
        details[name] = [
            {
                "event_index": index,
                "label": event_labels[index],
                "prediction": predictions.get(index, -1),
                "capture_count": len(grouped[index]),
                "correct": predictions.get(index) == event_labels[index],
            }
            for index in sorted(event_labels)
        ]

    output = {
        "contract": {
            "development_only": True,
            "label_blind_aggregation": True,
            "inputs": "capture order plus frozen NPU logits only",
            "denominator": len(events),
            "missing_counts_as_wrong": True,
        },
        "capture_count_histogram": dict(sorted(Counter(len(rows) for rows in grouped.values()).items())),
        "unmatched_replay_rows": sum(1 for item in replay if int(item["frame_id"]) not in event_by_frame),
        "summary": summary,
        "details": details,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
