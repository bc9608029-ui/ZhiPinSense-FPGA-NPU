"""Offline 12-vs-24 final evaluation and model recommendation (M16).

Aggregates, for each available candidate, the closed-set test metrics, fake-INT8
drop, channel-covariate OOD, and semantic OOD (Energy) report, then writes a
provisional offline recommendation.  The recommendation is a **model-side,
offline** comparison only — it never asserts a hardware/PASS verdict, and the
12-class candidate stays BLOCKED until its V2 checkpoint is imported.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from evaluation.evaluate_ood import evaluate_ood_12class, evaluate_ood_rml24
from evaluation.evaluate_rml24 import (
    evaluate_rml24,
    evaluate_rml24_channel_ood,
    fake_int8_report_rml24,
)
from training.utils import load_yaml, save_json

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


def run_final_evaluation(config_rml24: str, checkpoint_rml24: str, *,
                         twelve_class_config: str | None = None,
                         twelve_class_checkpoint: str | None = None,
                         output: str | None = None) -> dict[str, Any]:
    config = load_yaml(config_rml24)
    report: dict[str, Any] = {"candidates": {}}

    rml24_eval = evaluate_rml24(config, checkpoint_rml24, split="test")
    rml24 = {
        "checkpoint": checkpoint_rml24,
        "closed_set_test": _closed_set_summary(rml24_eval),
        "fake_int8": fake_int8_report_rml24(config, checkpoint_rml24),
        "channel_ood": evaluate_rml24_channel_ood(config, checkpoint_rml24),
        "semantic_ood": _compact(evaluate_ood_rml24(config, checkpoint_rml24, id_split="test")),
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
    from pathlib import Path
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--twelve-class-config", default=None)
    parser.add_argument("--twelve-class-checkpoint", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    report = run_final_evaluation(args.config, args.checkpoint,
                                  twelve_class_config=args.twelve_class_config,
                                  twelve_class_checkpoint=args.twelve_class_checkpoint,
                                  output=args.output)
    print(json.dumps(_compact(report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
