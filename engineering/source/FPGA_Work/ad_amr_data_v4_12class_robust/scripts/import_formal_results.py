"""Import and normalize the baseline twelve-class formal acceptance results.

PROVISIONAL tool.  Reads the AutoDL-produced ``acceptance.json`` (structure fixed
by the baseline ``scripts/run_ad_amr_v1_1_data_v3_12class_formal.py``) and
normalizes it into a flat, JSON-serializable form for the downstream analysis and
verification tools.  It never fabricates a metric: an absent field or an absent
optional per-sample predictions file is recorded as missing, not guessed.

Usage:
    python scripts/import_formal_results.py \
        --acceptance outputs/ad_amr_v1_1_data_v3_12class/formal/acceptance.json \
        --out outputs/ad_amr_v1_1_data_v3_12class/formal/imported_results.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_OOD_DOMAINS = (
    "cfo_strong", "phase_noise", "iq_imbalance", "multipath", "clipping", "multi_impairment",
)


def _metrics_section(report: dict, classes: list[str]) -> dict:
    metrics = dict(report.get("metrics", {}))
    metrics["classes"] = list(report.get("classes", classes))
    metrics["checkpoint"] = report.get("checkpoint")
    metrics["split"] = report.get("split")
    metrics["samples"] = report.get("samples")
    metrics["numeric_mode"] = report.get("numeric_mode")
    metrics["final_blind_test_accessed"] = report.get("final_blind_test_accessed", False)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--acceptance",
        default="outputs/ad_amr_v1_1_data_v3_12class/formal/acceptance.json",
    )
    parser.add_argument(
        "--out",
        default="outputs/ad_amr_v1_1_data_v3_12class/formal/imported_results.json",
    )
    args = parser.parse_args()

    acceptance_path = Path(args.acceptance)
    if not acceptance_path.is_file():
        raise SystemExit(f"acceptance.json not found: {acceptance_path}")

    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    classes = list(acceptance.get("class_contract", []))
    if not classes:
        raise SystemExit("acceptance.json has no class_contract")

    records = []
    for record in acceptance.get("records", []):
        ood = record.get("ood", {})
        normalized_ood: dict = {}
        for domain in EXPECTED_OOD_DOMAINS:
            normalized_ood[domain] = (
                _metrics_section(ood[domain], classes) if domain in ood else None
            )
        records.append({
            "seed": record.get("seed"),
            "checkpoint": record.get("checkpoint"),
            "validation": _metrics_section(record.get("validation", {}), classes),
            "fake_int8": _metrics_section(record.get("fake_int8", {}), classes),
            "ood": normalized_ood,
        })

    imported = {
        "source": str(acceptance_path),
        "release_input_hash": acceptance.get("release_input_hash"),
        "variant": acceptance.get("variant"),
        "class_contract": classes,
        "promoted": acceptance.get("promoted"),
        "gates": acceptance.get("gates", []),
        "records": records,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(imported, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"imported {len(records)} seed(s); ood domains: {list(EXPECTED_OOD_DOMAINS)} -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
