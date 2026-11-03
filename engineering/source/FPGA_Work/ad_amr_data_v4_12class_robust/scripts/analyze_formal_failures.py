"""Analyze the twelve-class formal OOD failures (facts only, no root cause).

PROVISIONAL tool.  From the imported results it computes, per OOD domain, the
macro-F1 drop relative to clean validation and the per-class accuracy deltas, then
ranks the classes most degraded in the three focus domains
(cfo_strong / multipath / multi_impairment).  It deliberately does NOT assert a
root cause or a fix; those conclusions require the AutoDL results plus the raw
per-sample predictions (which the baseline acceptance.json does not store, so the
confusion-pair section reports "unavailable" when they are absent).

Usage:
    python scripts/analyze_formal_failures.py \
        --imported outputs/ad_amr_v1_1_data_v3_12class/formal/imported_results.json \
        --out outputs/ad_amr_v1_1_data_v3_12class/formal/failure_analysis.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FOCUS_DOMAINS = ("cfo_strong", "multipath", "multi_impairment")
ALL_DOMAINS = ("cfo_strong", "phase_noise", "iq_imbalance", "multipath", "clipping", "multi_impairment")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--imported",
        default="outputs/ad_amr_v1_1_data_v3_12class/formal/imported_results.json",
    )
    parser.add_argument(
        "--out",
        default="outputs/ad_amr_v1_1_data_v3_12class/formal/failure_analysis.json",
    )
    args = parser.parse_args()

    path = Path(args.imported)
    if not path.is_file():
        raise SystemExit(f"imported results not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    classes = list(data.get("class_contract", []))
    records = data.get("records", [])

    analysis: dict = {"class_contract": classes, "domains": {}}
    for record in records:
        seed = record.get("seed")
        validation = record.get("validation", {})
        val_macro_f1 = validation.get("macro_f1")
        val_per_class = validation.get("per_class_accuracy")
        ood = record.get("ood", {})
        seed_entry: dict = {"seed": seed, "domains": {}}
        for domain in ALL_DOMAINS:
            report = ood.get(domain) or {}
            if not report:
                seed_entry["domains"][domain] = {"missing": True}
                continue
            macro_f1 = report.get("macro_f1")
            per_class = report.get("per_class_accuracy")
            drops = None
            if val_per_class is not None and per_class is not None:
                drops = [round(float(v) - float(d), 6) for v, d in zip(val_per_class, per_class)]
            entry = {
                "macro_f1": macro_f1,
                "macro_f1_drop": round(float(val_macro_f1) - float(macro_f1), 6)
                if val_macro_f1 is not None and macro_f1 is not None else None,
                "per_class_drop": drops,
                "confusion_matrix": "unavailable",
            }
            if drops is not None:
                ranked = sorted(range(len(classes)), key=lambda i: drops[i], reverse=True)
                entry["ranked_class_names"] = [classes[i] for i in ranked]
                entry["top_degraded"] = [
                    {"class": classes[i], "drop": drops[i]} for i in ranked[:5]
                ]
            seed_entry["domains"][domain] = entry
        analysis["domains"][str(seed)] = seed_entry

    analysis["confusion_matrix_available"] = False
    analysis["note"] = (
        "confusion pairs / root cause NOT asserted: baseline acceptance.json stores "
        "aggregate metrics only; raw per-sample predictions are required (see "
        "docs/NEEDS_AUTODL_RESULTS.md)."
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"classes: {classes}")
    for record in records:
        ood = record.get("ood", {})
        validation = record.get("validation", {})
        print(f"seed={record.get('seed')}")
        for domain in FOCUS_DOMAINS:
            report = ood.get(domain) or {}
            if not report:
                print(f"  {domain}: MISSING")
                continue
            drop = round(float(validation.get("macro_f1", 0.0)) - float(report.get("macro_f1", 0.0)), 4)
            top = analysis["domains"][str(record.get("seed"))]["domains"][domain].get("top_degraded", [])
            print(f"  {domain}: macro_f1={report.get('macro_f1')} drop={drop} top_degraded={top}")
    print("note:", analysis["note"])
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
