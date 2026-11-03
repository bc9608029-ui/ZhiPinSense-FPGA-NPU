"""Offline 12-vs-24 final evaluation and model recommendation (M16).

Aggregates, for each available candidate, the closed-set test metrics, fake-INT8
drop, channel-covariate OOD, and semantic OOD (Energy) report, then writes a
provisional offline recommendation.  The recommendation is a **model-side,
offline** comparison only — it never asserts a hardware/PASS verdict, and the
12-class candidate stays BLOCKED until its V2 checkpoint is imported.

The final evaluation is *frozen-threshold*: it reads the write-once
``ood_threshold_manifest.json`` and never re-fits the temperature nor re-selects
thresholds.  The RadioML ``test`` split and the ``ood_final_test`` family are
each read exactly once, guarded by a one-time access ledger
(``runs/final_evaluation/final_test_access.json``) that refuses a duplicate run.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from contracts.rml24_contract import LABEL_ORDER_24
from evaluation.closed_set_gate import acquire_closed_set_gate, complete_closed_set_gate
from evaluation.evaluate_ood import evaluate_ood_12class, evaluate_ood_final_rml24
from evaluation.evaluate_rml24 import (
    evaluate_rml24,
    evaluate_rml24_channel_ood,
    fake_int8_report_rml24,
)
from evaluation.final_test_gate import acquire_gate, complete_gate, file_sha256
from ood.threshold_manifest import read_threshold_manifest
from scripts._resolve_checkpoint import resolve_checkpoint
from training.utils import load_yaml, resolve_project_path, save_json
from v2.candidate_signature import label_contract_sha256

_DROP_KEYS = {"id_labels", "ood_scores", "decisions"}


def _compact(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _compact(value) for key, value in node.items() if key not in _DROP_KEYS}
    if isinstance(node, list):
        return [_compact(item) for item in node]
    return node


def _closed_set_summary(eval_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": eval_result["metrics"],
        "samples": eval_result["samples"],
        "split": eval_result["split"],
        "numeric_mode": eval_result["numeric_mode"],
    }


def _energy_auroc_energy_far(ood_report: dict[str, Any]) -> float | None:
    families = ood_report.get("families", {})
    energy = families.get("energy", {})
    far = energy.get("families", {}).get("far", {})
    auroc = far.get("ranking", {}).get("auroc")
    return float(auroc) if auroc is not None else None


def _generate_run_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"


def verify_final_identity(final_manifest: dict[str, Any],
                          threshold_manifest: dict[str, Any]) -> None:
    """Cross-check checkpoint / dataset / label identity between the two manifests.

    Fails closed on any disagreement, so a frozen threshold can never be applied
    to a different checkpoint, dataset, or label contract than the one it was
    locked on.
    """
    if str(final_manifest.get("checkpoint_sha256")) != str(threshold_manifest["checkpoint_sha256"]):
        raise RuntimeError(
            "checkpoint SHA mismatch: final manifest and threshold manifest disagree")
    if str(final_manifest.get("label_contract_sha256")) != str(threshold_manifest["model_sha256"]):
        raise RuntimeError(
            "label contract SHA mismatch: final manifest label_contract_sha256 != "
            "threshold manifest model_sha256")
    if str(final_manifest.get("dataset_sha256")) != str(threshold_manifest["calibration_dataset_sha256"]):
        raise RuntimeError(
            "dataset SHA mismatch: final manifest dataset_sha256 != "
            "threshold manifest calibration_dataset_sha256")


def run_final_evaluation(config_rml24: str, checkpoint_manifest_path: str,
                         threshold_manifest_path: str, *,
                         twelve_class_config: str | None = None,
                         twelve_class_checkpoint: str | None = None,
                         output: str | None = None,
                         gate_path: str | None = None,
                         run_id: str | None = None) -> dict[str, Any]:
    config = load_yaml(config_rml24)

    # Fail-closed identity chain before touching test data.
    final_manifest = json.loads(Path(checkpoint_manifest_path).read_text(encoding="utf-8"))
    checkpoint_path = resolve_checkpoint(checkpoint_manifest_path)  # SHA-verify checkpoint file
    threshold_manifest = read_threshold_manifest(threshold_manifest_path)  # fail-closed
    verify_final_identity(final_manifest, threshold_manifest)

    # One-time access ledger: refuse a duplicate final run up front.
    gate_path = gate_path or "runs/final_evaluation/final_test_access.json"
    run_id = run_id or os.environ.get("RUN_ID") or _generate_run_id()
    acquire_gate(
        gate_path,
        run_id=run_id,
        checkpoint_sha256=str(final_manifest["checkpoint_sha256"]),
        threshold_manifest_sha256=file_sha256(threshold_manifest_path),
        dataset_sha256=str(final_manifest["dataset_sha256"]),
    )

    report: dict[str, Any] = {"candidates": {}}

    # Read the RadioML test split exactly once and reuse its logits/labels/metrics.
    id_result = evaluate_rml24(config, checkpoint_path, split="test")
    rml24 = {
        "checkpoint": checkpoint_path,
        "closed_set_test": _closed_set_summary(id_result),
        "fake_int8": fake_int8_report_rml24(config, checkpoint_path),
        "channel_ood": evaluate_rml24_channel_ood(config, checkpoint_path),
        "semantic_ood": _compact(evaluate_ood_final_rml24(
            config, checkpoint_path, threshold_manifest_path, id_result=id_result,
        )),
    }
    report["candidates"]["rml24"] = rml24

    twelve_status = "BLOCKED_PENDING"
    if twelve_class_config and twelve_class_checkpoint:
        try:
            report["candidates"]["12class"] = _compact(
                evaluate_ood_12class(load_yaml(twelve_class_config), twelve_class_checkpoint)
            )
            twelve_status = "EVALUATED"
        except (RuntimeError, NotImplementedError) as exc:
            report["candidates"]["12class"] = {"blocked": str(exc)}

    energy_far = _energy_auroc_energy_far(rml24["semantic_ood"])
    accuracy = float(rml24["closed_set_test"]["metrics"]["accuracy"])
    finite = energy_far is not None and energy_far == energy_far and accuracy == accuracy
    if finite:
        recommendation_status = "RECOMMEND_24" if twelve_status == "BLOCKED_PENDING" else "BOTH"
    else:
        recommendation_status = "INSUFFICIENT"

    recommendation: dict[str, Any] = {
        "status": recommendation_status,
        "twelve_class_status": twelve_status,
        "rml24_test_accuracy": accuracy,
        "rml24_energy_far_auroc": energy_far,
        "rml24_fake_int8_accuracy_drop": float(rml24["fake_int8"]["accuracy_drop"]),
        "note": (
            "Offline, model-side recommendation only. The 12-class candidate is BLOCKED until "
            "its V2 checkpoint is imported; final selection additionally requires real NPU + real "
            "RF hardware verification, which is out of scope for this project."
        ),
    }
    report["recommendation"] = recommendation

    destination = output or "runs/final_evaluation/final_evaluation.json"
    save_json(_compact(report), destination)
    _write_recommendation_md(recommendation, rml24,
                             "runs/final_evaluation/OFFLINE_MODEL_RECOMMENDATION.md")

    complete_gate(gate_path, id_test_accessed=True, ood_final_test_accessed=True)
    return report


def _write_recommendation_md(recommendation: dict[str, Any], rml24: dict[str, Any],
                             path: str) -> None:
    lines: list[str] = []
    lines.append("# 离线 12/24 模型推荐（模型侧）\n")
    lines.append(f"- 推荐状态：`{recommendation['status']}`")
    lines.append(f"- 12 类候选状态：`{recommendation['twelve_class_status']}`")
    lines.append("")
    lines.append("## 24 类（RML2018_24）\n")
    lines.append(f"- 测试集准确率：`{recommendation['rml24_test_accuracy']:.6f}`")
    lines.append(f"- Energy 远 OOD AUROC：`{recommendation['rml24_energy_far_auroc']}`")
    lines.append(f"- fake-INT8 精度下降：`{recommendation['rml24_fake_int8_accuracy_drop']:.6f}`")
    lines.append("")
    lines.append("## 结论\n")
    lines.append(recommendation["note"])
    lines.append("")
    lines.append("> 本推荐仅为离线、模型侧比较；**绝不**代表上板/最终模型通过。")
    lines.append("> 硬件（NPU + 真实射频）验证通过前不得写入任何 PASS 标记。")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _confusion_matrix(targets: np.ndarray, predictions: np.ndarray,
                      num_classes: int) -> np.ndarray:
    """Row=target, column=prediction integer confusion matrix."""
    targets = np.asarray(targets, dtype=np.int64)
    predictions = np.asarray(predictions, dtype=np.int64)
    if targets.shape != predictions.shape:
        raise ValueError("targets and predictions shapes differ")
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    np.add.at(cm, (targets, predictions), 1)
    return cm


def _require_sha64(value: Any, key: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or \
            any(ch not in "0123456789abcdef" for ch in value):
        raise RuntimeError(f"final checkpoint manifest has invalid {key}")
    return value


def _verify_closed_set_identity(final_manifest: dict[str, Any]) -> None:
    """Fail-closed identity chain for the closed-set-only run.

    The checkpoint path/SHA are verified by ``resolve_checkpoint`` before this is
    called.  Here the dataset / label / config SHAs must all be present and 64-hex,
    and the label-contract SHA must equal the frozen 24-class contract — so the
    closed-set test can never run against a drifted checkpoint identity.
    """
    _require_sha64(final_manifest.get("checkpoint_sha256"), "checkpoint_sha256")
    _require_sha64(final_manifest.get("dataset_sha256"), "dataset_sha256")
    _require_sha64(final_manifest.get("label_contract_sha256"), "label_contract_sha256")
    _require_sha64(final_manifest.get("config_sha256"), "config_sha256")
    if str(final_manifest["label_contract_sha256"]) != label_contract_sha256():
        raise RuntimeError(
            "label contract SHA mismatch: final manifest != frozen 24-class contract")


def build_closed_set_report(id_result: dict[str, Any], final_manifest: dict[str, Any],
                            checkpoint_path: str | Path, run_id: str) -> dict[str, Any]:
    """Build the closed-set-only final report from a single ``evaluate_rml24(test)``.

    Derives the 24x24 confusion matrix, per-class accuracy with the real 24 label
    names, each class's dominant confusion target, and the Top-5 weakest classes —
    all from the one ID test result.  It never touches any OOD quantity.
    """
    metrics = dict(id_result["metrics"])
    labels = np.asarray(id_result["labels"], dtype=np.int64)
    logits = np.asarray(id_result["logits"], dtype=np.float32)
    predictions = logits.argmax(axis=1).astype(np.int64)
    cm = _confusion_matrix(labels, predictions, len(LABEL_ORDER_24))

    per_class_accuracy = [float(v) for v in metrics["per_class_accuracy"]]
    per_class = [
        {"class": LABEL_ORDER_24[i], "accuracy": per_class_accuracy[i]}
        for i in range(len(LABEL_ORDER_24))
    ]

    top_confusions: list[dict[str, Any]] = []
    for i in range(len(LABEL_ORDER_24)):
        row = cm[i].copy()
        row[i] = -1  # exclude the diagonal (self)
        j = int(row.argmax())
        top_confusions.append({
            "class": LABEL_ORDER_24[i],
            "top_confused_with": LABEL_ORDER_24[j],
            "count": int(cm[i, j]),
        })

    weakest_order = sorted(range(len(LABEL_ORDER_24)), key=lambda i: per_class_accuracy[i])
    top5_weakest = [
        {"class": LABEL_ORDER_24[i], "accuracy": per_class_accuracy[i]}
        for i in weakest_order[:5]
    ]

    return {
        "schema_version": 1,
        "mode": "closed_set_only",
        "run_id": run_id,
        "model": "RML2018_24",
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": str(final_manifest["checkpoint_sha256"]),
        "checkpoint_epoch": int(id_result.get("checkpoint_epoch", -1)),
        "selected_seed": int(final_manifest.get("selected_seed", -1)),
        "dataset_sha256": str(final_manifest["dataset_sha256"]),
        "label_contract_sha256": str(final_manifest["label_contract_sha256"]),
        "config_sha256": str(final_manifest["config_sha256"]),
        "split": id_result["split"],
        "split_samples": int(id_result["samples"]),
        "classes": list(LABEL_ORDER_24),
        "metrics": metrics,
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "top_confusions": top_confusions,
        "top5_weakest": top5_weakest,
        "final_blind_test_accessed": True,
        "ood_final_test_accessed": False,
    }


def _write_closed_set_report_md(report: dict[str, Any], path: str) -> None:
    metrics = report["metrics"]
    lines: list[str] = []
    lines.append("# 24 类闭集最终测试报告（closed-set only）\n")
    lines.append("")
    lines.append(f"- 模式：`{report['mode']}`")
    lines.append(f"- run_id：`{report['run_id']}`")
    lines.append(f"- checkpoint SHA：`{report['checkpoint_sha256']}`")
    lines.append(f"- dataset SHA：`{report['dataset_sha256']}`")
    lines.append(f"- label contract SHA：`{report['label_contract_sha256']}`")
    lines.append(f"- config SHA：`{report['config_sha256']}`")
    lines.append(f"- split：`{report['split']}`（样本数 {report['split_samples']}）")
    lines.append(f"- final_blind_test_accessed：`{report['final_blind_test_accessed']}`")
    lines.append(f"- ood_final_test_accessed：`{report['ood_final_test_accessed']}`")
    lines.append("")
    lines.append("## 总体指标\n")
    lines.append(f"- overall accuracy：`{metrics['accuracy']:.6f}`")
    lines.append(f"- macro-F1：`{metrics['macro_f1']:.6f}`")
    lines.append(f"- rated_0_20_accuracy：`{metrics['rated_0_20_accuracy']:.6f}`")
    lines.append(f"- high_10_20_accuracy：`{metrics['high_10_20_accuracy']:.6f}`")
    lines.append(f"- snr_0_accuracy：`{metrics['snr_0_accuracy']:.6f}`")
    lines.append(f"- min_per_class_accuracy：`{metrics['min_per_class_accuracy']:.6f}`")
    lines.append("")
    lines.append("## 每 SNR 准确率\n")
    for snr in sorted(metrics["per_snr_accuracy"], key=lambda v: float(v)):
        lines.append(f"- {snr} dB：`{metrics['per_snr_accuracy'][snr]:.6f}`")
    lines.append("")
    lines.append("## 每类别准确率（24 类真实标签）\n")
    lines.append("| 类别 | 准确率 |")
    lines.append("|---|---|")
    for entry in report["per_class"]:
        lines.append(f"| {entry['class']} | {entry['accuracy']:.6f} |")
    lines.append("")
    lines.append("## Top-5 最弱类别\n")
    for entry in report["top5_weakest"]:
        lines.append(f"- `{entry['class']}`：{entry['accuracy']:.6f}")
    lines.append("")
    lines.append("## 每类最主要混淆对象\n")
    for entry in report["top_confusions"]:
        lines.append(f"- `{entry['class']}` → `{entry['top_confused_with']}`（{entry['count']} 样本）")
    lines.append("")
    lines.append("## 混淆矩阵（24×24）\n")
    header = "| 真实\\预测 | " + " | ".join(report["classes"]) + " |"
    lines.append(header)
    lines.append("|---|" + "---|" * len(report["classes"]))
    for i, row in enumerate(report["confusion_matrix"]):
        lines.append(f"| {report['classes'][i]} | " + " | ".join(str(v) for v in row) + " |")
    lines.append("")
    lines.append("> 本报告为闭集（closed-set）测试，**不访问 ood_final_test**，")
    lines.append("> 不包含任何 OOD / 硬件通过标记。")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_closed_set_final_evaluation(config_rml24: str, checkpoint_manifest_path: str, *,
                                    output: str | None = None,
                                    report_md: str | None = None,
                                    gate_path: str | None = None,
                                    run_id: str | None = None) -> dict[str, Any]:
    """Closed-set-only final test: one ``evaluate_rml24(split="test")``, no OOD.

    Reads only the final checkpoint manifest, the frozen RadioML ``test`` split and
    the selected checkpoint.  It never calls any OOD entry point, never reads
    ``ood_threshold_manifest.json``, and never constructs ``ood_final_test``.  The
    ID ``test`` access is guarded by its own one-time ledger, fully independent of
    the OOD final ledger.
    """
    config = load_yaml(config_rml24)

    # Fail-closed identity chain before touching test data.
    final_manifest = json.loads(Path(checkpoint_manifest_path).read_text(encoding="utf-8"))
    checkpoint_path = resolve_checkpoint(checkpoint_manifest_path)  # SHA-verify checkpoint file
    _verify_closed_set_identity(final_manifest)

    # One-time access ledger — independent of the OOD final ledger.
    gate_path = gate_path or "runs/final_evaluation/rml24_closed_set_test_access.json"
    run_id = run_id or os.environ.get("RUN_ID") or _generate_run_id()
    acquire_closed_set_gate(
        gate_path,
        run_id=run_id,
        checkpoint_path=checkpoint_path,
        checkpoint_sha256=str(final_manifest["checkpoint_sha256"]),
        dataset_sha256=str(final_manifest["dataset_sha256"]),
        label_contract_sha256=str(final_manifest["label_contract_sha256"]),
        config_sha256=str(final_manifest["config_sha256"]),
    )

    # Read the RadioML test split exactly once; no OOD function is ever invoked.
    id_result = evaluate_rml24(config, checkpoint_path, split="test")

    report = build_closed_set_report(id_result, final_manifest, checkpoint_path, run_id)

    destination = resolve_project_path(output or "runs/final_evaluation/rml24_closed_set_final.json")
    save_json(report, destination)
    _write_closed_set_report_md(
        report, str(resolve_project_path(
            report_md or "runs/final_evaluation/RML24_CLOSED_SET_FINAL_REPORT.md")))

    complete_closed_set_gate(gate_path, output_sha256=file_sha256(destination))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--checkpoint-manifest", required=True)
    parser.add_argument("--threshold-manifest", default=None,
                        help="required unless --closed-set-only")
    parser.add_argument("--closed-set-only", action="store_true",
                        help="run only the 24-class closed-set test (no OOD final test)")
    parser.add_argument("--twelve-class-config", default=None)
    parser.add_argument("--twelve-class-checkpoint", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--gate-path", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    if args.closed_set_only:
        report = run_closed_set_final_evaluation(
            args.config, args.checkpoint_manifest,
            output=args.output, gate_path=args.gate_path, run_id=args.run_id,
        )
    else:
        if not args.threshold_manifest:
            parser.error("--threshold-manifest is required unless --closed-set-only")
        report = run_final_evaluation(
            args.config, args.checkpoint_manifest, args.threshold_manifest,
            twelve_class_config=args.twelve_class_config,
            twelve_class_checkpoint=args.twelve_class_checkpoint,
            output=args.output, gate_path=args.gate_path, run_id=args.run_id,
        )
    print(json.dumps(_compact(report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
