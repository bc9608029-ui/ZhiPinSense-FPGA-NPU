#!/usr/bin/env python3
"""Export evidence-backed UI JSONL without fabricating unavailable IQ/spectrum."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from ui_event import build_ui_event  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected", type=Path, help="Optional self-test truth; never used by the receiver")
    parser.add_argument("--confidence-threshold", type=float, default=0.55)
    args = parser.parse_args()

    board = json.loads(args.board_results.read_text(encoding="utf-8-sig"))
    truth = None
    if args.expected is not None:
        expected = json.loads(args.expected.read_text(encoding="utf-8-sig"))
        truth = {int(row["seq"]): row for row in expected["records"]}

    events = []
    for row in board.get("records", []):
        seq = int(row["seq"])
        self_test = None
        if truth is not None:
            target = truth[seq]
            pred = row.get("arms", {}).get("candidate", {}).get("pred", -1)
            self_test = {
                "enabled": True,
                "expected_index": int(target["class_index"]),
                "expected_class": target["class_name"],
                "correct": pred == int(target["class_index"]),
                "progress_current": len(events) + 1,
                "progress_total": len(board["records"]),
            }
        event = build_ui_event(
            seq,
            row.get("arms", {}).get("candidate", {}),
            timestamp_us=seq * 100_000,
            confidence_threshold=args.confidence_threshold,
            self_test=self_test,
        )
        events.append(event)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n" for event in events), encoding="utf-8")
    summary = {
        "token": "RML24_FINAL_UI_REPLAY_EXPORT_V1",
        "events": len(events),
        "identified": sum(event["state"] == "IDENTIFIED" for event in events),
        "low_confidence": sum(event["state"] == "LOW_CONFIDENCE" for event in events),
        "failed": sum(event["state"] == "RECOVERY_FAILED" for event in events),
        "iq_frames": sum(event["iq_valid"] for event in events),
        "spectrum_frames": sum(event["spectrum_valid"] for event in events),
        "self_test": truth is not None,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if len(events) == 240 else 2


if __name__ == "__main__":
    raise SystemExit(main())

