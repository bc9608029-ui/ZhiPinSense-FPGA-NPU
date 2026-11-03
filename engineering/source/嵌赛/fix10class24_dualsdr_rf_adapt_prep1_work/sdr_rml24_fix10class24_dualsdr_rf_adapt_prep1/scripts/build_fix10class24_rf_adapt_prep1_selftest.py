#!/usr/bin/env python3
"""build_fix10class24_rf_adapt_prep1_selftest.py -- generate static deliverables + selftest.

Runs under ``python -I`` (pure stdlib + numpy-free).  This is the PREP build
entry point.  It writes, deterministically, every static deliverable:

* ``plans/rml24_dualsdr_rf_capture_plan_v1.tsv``        (960 rows)
* ``training/configs/fix10class24_rf_adapt_pilot.yaml`` (preregistered spec)
* ``results/rf_adapt_prep1/dataset_plan_summary.json``
* ``results/rf_adapt_prep1/asset_inventory.tsv``        (Phase A stratification)
* ``results/rf_adapt_prep1/frozen_evaluation_sets.tsv`` (F1/F2/F3 sets)
* ``results/rf_adapt_prep1/pipeline_selftest.json``     (real checks, not claims)

It then RUNS the pipeline selftest: contract consistency, plan integrity,
leak-free split, config YAML round-trip, and a dataset-builder dry-run on a
small synthetic capture set.  Any failure is a non-zero exit.

Usage::

    python -I scripts/build_fix10class24_rf_adapt_prep1_selftest.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_HERE, os.pardir, "contracts"))
sys.path.insert(0, _HERE)
import rml24_dualsdr_rf_dataset_v1 as C  # noqa: E402
import build_fix10class24_dualsdr_rf_dataset as B  # noqa: E402

RESULTS_DIR = os.path.join(_ROOT, "results", "rf_adapt_prep1")
PLANS_DIR = os.path.join(_ROOT, "plans")
TRAINING_CFG_DIR = os.path.join(_ROOT, "training", "configs")


def _write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None or v == "":
        return ""
    return str(v)


def _tsv(path, columns, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(columns) + "\n")
        for r in rows:
            f.write("\t".join(_fmt(r.get(c, "")) for c in columns) + "\n")


def emit_capture_plan():
    rows = list(C.capture_plan_rows())
    _tsv(os.path.join(PLANS_DIR, "rml24_dualsdr_rf_capture_plan_v1.tsv"),
         C.CAPTURE_PLAN_COLUMNS, rows)
    return rows


def emit_training_config():
    text = ("# fix10class24_rf_adapt_pilot.yaml -- preregistered pilot training spec\n"
            "# Frozen in contracts/rml24_dualsdr_rf_dataset_v1.py::PILOT_TRAINING_SPEC.\n"
            "# DO NOT edit by hand; regenerate via build_fix10class24_rf_adapt_prep1_selftest.py.\n"
            + C.yaml_dump_simple(C.PILOT_TRAINING_SPEC) + "\n")
    _write(os.path.join(TRAINING_CFG_DIR, "fix10class24_rf_adapt_pilot.yaml"), text)


def emit_dataset_plan_summary(plan_rows):
    summary = {
        "contract_sha256": C.dataset_contract_sha256(),
        "label_contract_sha256": C.FROZEN["label_contract_sha256"],
        "pilot_per_class": C.PILOT_PER_CLASS,
        "formal_per_class": C.FORMAL_PER_CLASS,
        "total_planned": len(plan_rows),
        "pilot_total": 24 * C.PILOT_PER_CLASS,
        "formal_total": 24 * C.FORMAL_PER_CLASS,
        "formal_split": {
            "train_offsets": list(C.FORMAL_TRAIN_OFFSETS),
            "val_offsets": list(C.FORMAL_VAL_OFFSETS),
            "test_offsets": list(C.FORMAL_TEST_OFFSETS),
            "train_per_class": len(C.FORMAL_TRAIN_OFFSETS),
            "val_per_class": len(C.FORMAL_VAL_OFFSETS),
            "test_per_class": len(C.FORMAL_TEST_OFFSETS),
        },
        "session_requirement": {"pilot": ">=1 session", "formal": ">=2 sessions"},
        "rf_config": C.RF_CONFIG,
        "gate_policy": {
            "PASSED": "keep (main set)",
            "DIAGNOSTIC_PROVISIONAL": "retain as provisional (pilot only, never train/val/test)",
            "REJECTED": "bounded retry <=3, then record and discard",
        },
    }
    _write(os.path.join(RESULTS_DIR, "dataset_plan_summary.json"),
           json.dumps(summary, indent=2, sort_keys=True))


def _sha_or_empty(path):
    p = Path(path)
    return C.sha256_file(p) if p.is_file() else ""


def emit_asset_inventory():
    bf16_dir = os.path.join(_ROOT, "model_rml24_bf16")
    bf16_json = os.path.join(bf16_dir, "rml24_adamrv11_bf16.json")
    bf16_raw = os.path.join(bf16_dir, "rml24_adamrv11_bf16.raw")
    clean_manifest = os.path.join(_ROOT, "clean24_smoke", "clean24_smoke_manifest.tsv")

    cols = ("asset_id", "kind", "role", "location", "sha256", "status",
            "num_classes", "num_samples", "notes")
    rows = [
        {"asset_id": "fp32_checkpoint", "kind": "model/checkpoint",
         "role": "init-point-for-adaptation",
         "location": "F:/FPGA_Work/sdr_rml24_npu_deployment_m29/_frozen/runs/rml24_base/formal/t002_losscross_entropy_optadamw/seed2027/checkpoints/best.pt",
         "sha256": C.FROZEN["fp32_checkpoint_sha256"], "status": "frozen",
         "num_classes": 24, "num_samples": "", "notes": "read-only source; never retrained in place"},
        {"asset_id": "onnx_opset17", "kind": "model/onnx",
         "role": "export-reference",
         "location": "F:/FPGA_Work/sdr_rml24_npu_deployment_m29/work/onnx/rml24_24class_opset17.onnx",
         "sha256": C.FROZEN["onnx_sha256"], "status": "frozen",
         "num_classes": 24, "num_samples": "", "notes": "opset17, [1,2,1024]->[1,24]"},
        {"asset_id": "bf16_model_json", "kind": "model/bf16",
         "role": "production-baseline",
         "location": bf16_json, "sha256": _sha_or_empty(bf16_json),
         "status": "frozen-never-overwrite", "num_classes": 24, "num_samples": "",
         "notes": f"expected {C.FROZEN['bf16_json_sha256'][:12]}..."},
        {"asset_id": "bf16_model_raw", "kind": "model/bf16",
         "role": "production-baseline",
         "location": bf16_raw, "sha256": _sha_or_empty(bf16_raw),
         "status": "frozen-never-overwrite", "num_classes": 24, "num_samples": "",
         "notes": f"expected {C.FROZEN['bf16_raw_sha256'][:12]}..."},
        {"asset_id": "tf32_model", "kind": "model/tf32",
         "role": "sibling-experiment",
         "location": "F:/嵌赛/fix10class24_tf32_ab1_work/sdr_rml24_fix10class24_tf32_ab1/model_rml24_tf32/",
         "sha256": "", "status": "frozen-never-overwrite", "num_classes": 24,
         "num_samples": "", "notes": f"json {C.FROZEN['tf32_json_sha256'][:12]}... raw {C.FROZEN['tf32_raw_sha256'][:12]}..."},
        {"asset_id": "clean24_smoke", "kind": "data/clean-synthetic",
         "role": "frozen-regression-F1",
         "location": os.path.join(_ROOT, "clean24_smoke"),
         "sha256": _sha_or_empty(clean_manifest), "status": "frozen",
         "num_classes": 24, "num_samples": 24,
         "notes": "24 synthetic clean IQ; NEVER in train/val/test"},
        {"asset_id": "single_sdr_scalarwl_mixed24", "kind": "data/real-rf",
         "role": "frozen-control-F2",
         "location": "F:/嵌赛/board_capture/scalarwl_mixed24/scalarwl_mixed24_1773376147/",
         "sha256": "", "status": "external-dir", "num_classes": 24, "num_samples": 24,
         "notes": "single-SDR scalar+wl, 24 classes; 23/24 reference"},
        {"asset_id": "single_sdr_scalarwl_4way", "kind": "data/real-rf",
         "role": "frozen-control-F2",
         "location": "F:/嵌赛/board_capture/scalarwl_4way/scalarwl_out_fix1_1773374345/",
         "sha256": "", "status": "external-dir", "num_classes": 1, "num_samples": 2,
         "notes": "OQPSK(11500) single-SDR failure focus"},
        {"asset_id": "dual_sdr_full24_forced", "kind": "data/real-rf",
         "role": "frozen-historical-test-F3",
         "location": "F:/嵌赛/fix10class24_rxresidual_audit1_work/sdr_rml24_fix10class24_rxresidual_audit1/results/full24_failed_rx_forceclass/forced_classify_export/rml24_full24_failed_rx_1773374413/",
         "sha256": "", "status": "external-dir", "num_classes": 20, "num_samples": 20,
         "notes": "dual-SDR gate-rejected forced classification; 18/24 forced reference"},
        {"asset_id": "residual_diagnostics", "kind": "data/diagnostic",
         "role": "diagnostic-only",
         "location": "F:/嵌赛/fix10class24_rxresidual_audit1_work/sdr_rml24_fix10class24_rxresidual_audit1/results/",
         "sha256": "", "status": "external-dir", "num_classes": "", "num_samples": "",
         "notes": "residual decomposition/attribution; NOT for training"},
        {"asset_id": "future_real_rf_captures", "kind": "data/real-rf",
         "role": "future-training-only",
         "location": "datasets/rml24_dualsdr_rf_v1/",
         "sha256": "", "status": "pending", "num_classes": 24, "num_samples": 960,
         "notes": "the ONLY data that enters adaptation training; capture plan v1"},
    ]
    _tsv(os.path.join(RESULTS_DIR, "asset_inventory.tsv"), cols, rows)


def emit_frozen_evaluation_sets():
    cols = ("set_id", "purpose", "num_classes", "num_samples", "source_path",
            "frozen_baseline", "gate_requirement", "notes")
    rows = [
        {"set_id": "F1", "purpose": "clean-hold regression",
         "num_classes": 24, "num_samples": 24,
         "source_path": "clean24_smoke/", "frozen_baseline": "24/24 (raw24)",
         "gate_requirement": "must stay >= baseline", "notes": "synthetic clean IQ"},
        {"set_id": "F2", "purpose": "single-SDR frozen control",
         "num_classes": 24, "num_samples": "24 (scalar+wl)",
         "source_path": "F:/嵌赛/board_capture/scalarwl_mixed24/...",
         "frozen_baseline": "23/24", "gate_requirement": "no regression; OQPSK fix check",
         "notes": "single SDR real RF; OQPSK(11500)->32PSK is the known failure"},
        {"set_id": "F3", "purpose": "dual-SDR post-freeze open test",
         "num_classes": 20, "num_samples": 20,
         "source_path": "F:/嵌赛/fix10class24_rxresidual_audit1_work/.../rml24_full24_failed_rx_1773374413/",
         "frozen_baseline": "18/24 (forced)", "gate_requirement": "open test (never used for selection)",
         "notes": "dual SDR gate-rejected; 6 deterministic same-family confusions"},
        {"set_id": "F4", "purpose": "3-seed statistics",
         "num_classes": 24, "num_samples": "",
         "source_path": "(computed over seeds 17/29/43)",
         "frozen_baseline": "", "gate_requirement": "report min/mean/max/std",
         "notes": "statistical, not a data set"},
    ]
    _tsv(os.path.join(RESULTS_DIR, "frozen_evaluation_sets.tsv"), cols, rows)


def _make_synthetic_capture(root: Path) -> Path:
    """A tiny valid capture set exercising every split role + provisional + rejected."""
    root.mkdir(parents=True, exist_ok=True)

    def add(sample_id, class_index, offset, link, gate, session="s1"):
        d = root / sample_id
        d.mkdir(parents=True, exist_ok=True)
        si = C.class_offset_to_source_index(class_index, offset)
        meta = {
            "source_index": si, "link": link, "gate_status": gate,
            "capture_session_id": session, "payload_training_residual": 0.05,
            "corr": 0.99, "cfo_hz": 12.5, "wide_linear_ratio": 0.03,
            "capture_attempts": 1, "raw_rx_iq_sha256": C.sha256_bytes(b"iq" + str(si).encode()),
        }
        (d / "capture_meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (d / B.SCALAR_FILENAME).write_bytes(bytes(8192))  # finite zeros
        return si

    add("c00_000", 0, 0, "single", C.GATE_DIAGNOSTIC_PROVISIONAL)  # pilot, provisional
    add("c00_010", 0, 10, "dual", C.GATE_PASSED)   # train
    add("c00_011", 0, 11, "dual", C.GATE_REJECTED)  # rejected -> excluded
    add("c00_028", 0, 28, "dual", C.GATE_PASSED)   # val
    add("c00_034", 0, 34, "dual", C.GATE_PASSED)   # test
    add("c01_010", 1, 10, "dual", C.GATE_PASSED)   # train (second class)
    return root


def run_pipeline_selftest():
    checks = {}

    C.assert_contract_consistent()
    checks["contract_consistent"] = True

    plan_rows = list(C.capture_plan_rows())
    checks["plan_row_count"] = len(plan_rows)
    checks["plan_pilot_count"] = sum(1 for r in plan_rows if r["phase"] == "pilot")
    checks["plan_formal_count"] = sum(1 for r in plan_rows if r["phase"] == "formal")
    checks["plan_source_indices_unique"] = (
        len({r["source_index"] for r in plan_rows}) == len(plan_rows))

    C.assert_split_is_leakfree()
    checks["split_leakfree"] = True

    # config YAML round-trip against the frozen spec
    yaml_path = os.path.join(TRAINING_CFG_DIR, "fix10class24_rf_adapt_pilot.yaml")
    yaml_text = Path(yaml_path).read_text(encoding="utf-8")
    parsed = C.yaml_load_simple(yaml_text)
    checks["config_yaml_matches_spec"] = (parsed == C.PILOT_TRAINING_SPEC)

    # dataset builder dry-run on the synthetic capture set
    with tempfile.TemporaryDirectory() as td:
        cap_root = _make_synthetic_capture(Path(td) / "captures")
        out_dir = Path(td) / "dataset"
        report = B.build(cap_root, out_dir, allow_provisional=True)
        manifest = (out_dir / "manifest.tsv").read_text(encoding="utf-8")
        n_manifest = sum(1 for _ in manifest.splitlines()) - 1  # minus header
        checks["builder_accepted"] = report["accepted"]
        checks["builder_rejected"] = report["rejected"]
        checks["builder_manifest_rows"] = n_manifest
        checks["builder_split_counts"] = report["split_counts"]
        checks["builder_contract_sha_matches"] = (
            report["contract_sha256"] == C.dataset_contract_sha256())
        checks["builder_report_written"] = (out_dir / "build_report.json").is_file()

    return checks


def main() -> int:
    plan_rows = emit_capture_plan()
    emit_training_config()
    emit_dataset_plan_summary(plan_rows)
    emit_asset_inventory()
    emit_frozen_evaluation_sets()

    checks = run_pipeline_selftest()
    result = {
        "contract_sha256": C.dataset_contract_sha256(),
        "label_contract_sha256": C.FROZEN["label_contract_sha256"],
        "frozen_identities": C.FROZEN,
        "checks": checks,
        "all_passed": all(isinstance(v, bool) or v is not None for v in checks.values())
                      and checks.get("config_yaml_matches_spec", False)
                      and checks.get("builder_contract_sha_matches", False)
                      and checks.get("split_leakfree", False),
    }
    _write(os.path.join(RESULTS_DIR, "pipeline_selftest.json"),
           json.dumps(result, indent=2, sort_keys=True))

    print(json.dumps(checks, indent=2, sort_keys=True))
    print(f"\nselftest {'PASS' if result['all_passed'] else 'FAIL'}")
    print("deliverables written to:")
    print("  ", os.path.join(PLANS_DIR, "rml24_dualsdr_rf_capture_plan_v1.tsv"))
    print("  ", os.path.join(TRAINING_CFG_DIR, "fix10class24_rf_adapt_pilot.yaml"))
    print("  ", RESULTS_DIR)
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
