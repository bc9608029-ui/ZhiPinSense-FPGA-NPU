"""Outlier Exposure + Energy seed strategy (1 + 2) with a promotion gate.

OE is expensive and can degrade closed-set ID accuracy, so it is gated instead of
being run unconditionally:

1. Train OE with the frozen first seed (2026) — the *verify* run.
2. Compare its ID accuracy (macro-F1 / rated_0_20_accuracy) and its Energy OOD
   (AUROC / FPR@95TPR / OSCR on the ``far`` family) against the frozen baseline
   model.
3. Promote to the remaining seeds (2027, 2028) only when ID degradation is within
   tolerance AND at least one OOD metric improves by the frozen margin.  Otherwise
   REJECT and keep the Energy baseline — ID degradation is never hidden.

Budget: the verify run is 1 run; promotion adds 2 (2027, 2028), so the OE phase is
at most 3 runs, which with the 3 formal runs stays at the 6-run cap.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from training.utils import load_yaml, save_json

OE_FIRST_SEED = 2026
OE_EXTRA_SEEDS = (2027, 2028)

ID_DEGRADATION_TOL = 0.01
OOD_AUROC_GAIN = 0.02
OOD_FPR95_GAIN = 0.05
OOD_OSCR_GAIN = 0.02


def id_metrics_from_result(result: dict[str, Any]) -> dict[str, float]:
    """Extract the closed-set ID metrics used by the promotion gate."""
    metrics = (result.get("baseline") or {}).get("metrics") or {}
    return {
        "macro_f1": float(metrics.get("macro_f1", 0.0)),
        "rated_0_20_accuracy": float(metrics.get("rated_0_20_accuracy", 0.0)),
    }


def energy_far_metrics(ood_report: dict[str, Any]) -> dict[str, float]:
    """Extract Energy AUROC / FPR95 / OSCR on the ``far`` (final OOD test) family."""
    families = (ood_report.get("families") or {}).get("energy") or {}
    far = (families.get("families") or {}).get("far") or {}
    ranking = far.get("ranking") or {}
    oscr = far.get("oscr") or {}
    return {
        "auroc": float(ranking.get("auroc", 0.0)),
        "fpr95": float(ranking.get("fpr95", 0.0)),
        "oscr": float(oscr.get("auc_ccr_fpr", 0.0)),
    }


def decide_oe_promotion(baseline_id: dict[str, float], oe_id: dict[str, float],
                        baseline_ood: dict[str, float], oe_ood: dict[str, float]) -> dict[str, Any]:
    """Apply the frozen OE promotion gate (fail-closed toward REJECT)."""
    macro_drop = baseline_id["macro_f1"] - oe_id["macro_f1"]
    rated_drop = baseline_id["rated_0_20_accuracy"] - oe_id["rated_0_20_accuracy"]
    gains = {
        "auroc": oe_ood["auroc"] - baseline_ood["auroc"],
        "fpr95": baseline_ood["fpr95"] - oe_ood["fpr95"],  # positive = lower FPR@95TPR
        "oscr": oe_ood["oscr"] - baseline_ood["oscr"],
    }
    reasons: list[str] = []
    if macro_drop > ID_DEGRADATION_TOL:
        reasons.append(f"id_macro_f1_drop={macro_drop:.4f}>{ID_DEGRADATION_TOL}")
    if rated_drop > ID_DEGRADATION_TOL:
        reasons.append(f"id_rated_acc_drop={rated_drop:.4f}>{ID_DEGRADATION_TOL}")
    improved = []
    if gains["auroc"] >= OOD_AUROC_GAIN:
        improved.append("auroc")
    if gains["fpr95"] >= OOD_FPR95_GAIN:
        improved.append("fpr95")
    if gains["oscr"] >= OOD_OSCR_GAIN:
        improved.append("oscr")
    if not improved:
        reasons.append("no_ood_gain")
    decision = "PROMOTE" if not reasons else "REJECT"
    return {
        "decision": decision,
        "id_degradation": {"macro_f1_drop": macro_drop, "rated_acc_drop": rated_drop},
        "ood_gain": gains,
        "improved": improved,
        "reasons": reasons,
    }


def build_oe_report(baseline_id: dict[str, float], oe_id: dict[str, float],
                    baseline_ood: dict[str, float], oe_ood: dict[str, float],
                    decision: dict[str, Any]) -> dict[str, Any]:
    """Assemble the ``oe_pilot_seed2026_report.json`` payload."""
    return {
        "oe_seed": OE_FIRST_SEED,
        "baseline_id": baseline_id,
        "oe_id": oe_id,
        "baseline_ood_energy_far": baseline_ood,
        "oe_ood_energy_far": oe_ood,
        "tolerances": {
            "id_degradation_tol": ID_DEGRADATION_TOL,
            "auroc_gain": OOD_AUROC_GAIN,
            "fpr95_gain": OOD_FPR95_GAIN,
            "oscr_gain": OOD_OSCR_GAIN,
        },
        **decision,
    }


def _rml24_node(ood_report: dict[str, Any]) -> dict[str, Any]:
    # run_ood_baselines wraps the 24-class report under "rml24".
    if isinstance(ood_report.get("rml24"), dict):
        return ood_report["rml24"]
    return ood_report


def _result_path_for_checkpoint(checkpoint_path: str) -> str:
    cp = Path(checkpoint_path)  # <...>/seed<N>/checkpoints/best.pt
    return str(cp.parent.parent / "logs" / "result.json")


def run_oe_seed_strategy(oe_config_path: str | Path,
                         baseline_manifest_path: str | Path,
                         baseline_ood_path: str | Path,
                         *, output_root: str | Path | None = None,
                         count_per_modulation: int = 256,
                         train_oe: Callable[..., dict[str, Any]] | None = None,
                         evaluate_oe_ood: Callable[..., dict[str, Any]] | None = None,
                         ) -> dict[str, Any]:
    """Run the gated OE 1+2 seed strategy and write the decision artifacts."""
    from evaluation.evaluate_ood import evaluate_ood_rml24
    from training.oe_run import run_oe_trial

    train_oe = train_oe or run_oe_trial
    evaluate_oe_ood = evaluate_oe_ood or evaluate_ood_rml24

    oe_cfg = load_yaml(oe_config_path)
    root = Path(output_root or oe_cfg["output_root"])

    manifest = json.loads(Path(baseline_manifest_path).read_text(encoding="utf-8"))
    baseline_result = json.loads(
        Path(_result_path_for_checkpoint(manifest["checkpoint_path"])).read_text(encoding="utf-8"),
    )
    baseline_ood = json.loads(Path(baseline_ood_path).read_text(encoding="utf-8"))

    # 1. Verify run: train OE with the frozen first seed.
    oe_result = train_oe(oe_cfg, "seed2026", root, seed=OE_FIRST_SEED)
    oe_checkpoint = oe_result["checkpoint_path"]

    # 2. OE semantic OOD (Energy far family).
    oe_ood = evaluate_oe_ood(oe_cfg, oe_checkpoint, count_per_modulation=count_per_modulation)

    baseline_id = id_metrics_from_result(baseline_result)
    oe_id = id_metrics_from_result(oe_result)
    baseline_energy = energy_far_metrics(_rml24_node(baseline_ood))
    oe_energy = energy_far_metrics(oe_ood)

    decision = decide_oe_promotion(baseline_id, oe_id, baseline_energy, oe_energy)
    report = build_oe_report(baseline_id, oe_id, baseline_energy, oe_energy, decision)
    save_json(report, root / "oe_pilot_seed2026_report.json")

    if decision["decision"] == "PROMOTE":
        print("OE_DECISION result=PROMOTE", flush=True)
        for seed in OE_EXTRA_SEEDS:
            train_oe(oe_cfg, f"seed{seed}", root, seed=seed)
        print("OE_DECISION extra_seeds=2027,2028 trained", flush=True)
    else:
        print("OE_DECISION result=REJECT", flush=True)
    return report


__all__ = [
    "OE_FIRST_SEED", "OE_EXTRA_SEEDS", "id_metrics_from_result", "energy_far_metrics",
    "decide_oe_promotion", "build_oe_report", "run_oe_seed_strategy",
]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--oe-config", default="configs/oe_energy.yaml")
    parser.add_argument("--baseline-manifest", required=True)
    parser.add_argument("--baseline-ood", required=True)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--count-per-modulation", type=int, default=256)
    args = parser.parse_args()
    report = run_oe_seed_strategy(
        args.oe_config, args.baseline_manifest, args.baseline_ood,
        output_root=args.output_root, count_per_modulation=args.count_per_modulation,
    )
    print(f"oe_decision: {report['decision']} reasons={report['reasons']}")


if __name__ == "__main__":
    main()

