"""Freeze the winning V3.3 Stage-1 candidate using a pre-written, fixed rule.

The rule is deliberately fixed (not learned, not tuned against any test set) and
ranks the candidates on the *validation* namespace (never the development test or
the final blind set):

    1. two-seed mean macro-F1 (descending);
    2. worst-seed macro-F1 (descending) — no lucky seed may carry the win;
    3. worst-domain OOD macro-F1 (descending) — lowest across OOD domains;
    4. two-seed mean accuracy (descending);
    5. two-seed mean QAM (16QAM/64QAM) accuracy (descending);
    6. worst-class regression vs A0 (ascending — lower drop is better);
    7. FPGA-sim-vs-FP32 accuracy gap (ascending — lower gap is better);
    tie-break: variant name ascending (deterministic).

Every regression baseline is the **same-seed A0** (frozen V2) inferred on the
identical ``v3_3_validation`` data: candidate seed 2026 is compared against A0
seed 2026, seed 2027 against A0 seed 2027, and each OOD domain against the
same-seed, same-domain A0 result.  The Stage-1 ranking therefore never depends on
the acceptance YAML's V2 *test*-namespace per-class numbers.

Promotion is gated by a set of **hard pilot gates** (in addition to the
improvement threshold), all measured against the same-seed A0 baseline:

    #1 two-seed mean validation macro-F1 improves over A0 by >= threshold;
    #2 every seed's macro-F1 is not below the same-seed A0 macro-F1;
    #3 every seed's worst-domain OOD macro-F1 drops at most ``maximum_ood_regression``
       below the same-seed A0 worst-domain;
    #4 every seed, every class validation accuracy drops at most
       ``maximum_per_class_accuracy_drop`` below the same-seed A0 class accuracy;
    #5 every seed's FPGA-sim accuracy gap <= ``maximum_fpga_sim_accuracy_gap``;
    #6 every seed's FPGA-sim macro-F1 gap <= ``maximum_fpga_sim_macro_f1_gap``;
    #7 no NaN / Inf / timeout / missing metric.

Any failure of a hard gate disqualifies the trained candidate from promotion (the
winner then falls back to A0 / frozen V2).  A trained candidate that passes the
hard gates but not the improvement threshold is selected but ``promoted: false``.
The exact failed gate is reported so the pilot's go/no-go is auditable.

``test`` and ``v3_3_final_blind_test`` are never consulted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import yaml

from training.qam_aware_v3_3_utils import write_text_lf
from training.utils import resolve_project_path

SELECTION_RULE = "fixed_two_seed_lexicographic"
SELECTION_SCOPE = "validation namespace only; test and v3_3_final_blind_test were not accessed"

DEFAULT_PILOT_GATES = {
    "maximum_ood_regression": 0.01,
    "maximum_per_class_accuracy_drop": 0.03,
    "maximum_fpga_sim_accuracy_gap": 0.03,
    "maximum_fpga_sim_macro_f1_gap": 0.03,
}


def _is_finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _a0_record(summary: dict) -> dict:
    for record in summary.get("variants", []):
        if not bool(record.get("trained", True)):
            return record
    return None


def extract_a0_baseline(summary: dict) -> dict:
    """Per-seed A0 (frozen V2) baseline inferred on the validation namespace.

    Returns a mapping ``{seed_key: {"macro_f1", "per_class_accuracy",
    "worst_domain_macro_f1", "domains"}}``.  ``domains`` maps each OOD domain name
    to its A0 macro-F1 and per-class accuracy, so every candidate OOD domain is
    compared against the *same-seed, same-domain* A0 result.
    """

    a0 = _a0_record(summary)
    if a0 is None:
        raise RuntimeError("Stage-1 summary must contain a non-trained A0 baseline variant.")
    baseline: dict = {}
    for seed_key, seed in a0["seeds"].items():
        ood = seed.get("ood", {}) or {}
        domains = {}
        for domain in ood.get("domains", []):
            domains[str(domain["domain"])] = {
                "macro_f1": float(domain["macro_f1"]),
                "per_class_accuracy": {k: float(v) for k, v in (domain.get("per_class_accuracy", {}) or {}).items()},
            }
        baseline[str(seed_key)] = {
            "macro_f1": float(seed["macro_f1"]),
            "per_class_accuracy": {k: float(v) for k, v in (seed.get("per_class_accuracy", {}) or {}).items()},
            "worst_domain_macro_f1": float(ood.get("worst_domain_macro_f1", seed["macro_f1"])),
            "domains": domains,
        }
    return baseline


def _a0_mean_macro_f1(a0_baseline: dict) -> float:
    values = [float(seed["macro_f1"]) for seed in a0_baseline.values()]
    return sum(values) / len(values)


def _ranked_metrics(record: dict, a0_baseline: dict) -> dict:
    seed_items = list(record["seeds"].items())
    if not seed_items:
        raise RuntimeError(f"Ablation candidate {record['variant']!r} has no seed records.")

    macro_f1s = [float(seed.get("macro_f1", float("nan"))) for _, seed in seed_items]
    accuracies = [float(seed.get("accuracy", float("nan"))) for _, seed in seed_items]
    qams = [float(seed.get("qam_mean_accuracy", float("nan"))) for _, seed in seed_items]
    worst_domain_f1s = [
        float(seed.get("ood", {}).get("worst_domain_macro_f1", seed.get("macro_f1", float("nan"))))
        for _, seed in seed_items
    ]

    worst_regression = 0.0
    for seed_key, seed in seed_items:
        a0 = a0_baseline.get(str(seed_key))
        if a0 is None:
            continue
        per_class = seed.get("per_class_accuracy", {}) or {}
        for name, base in a0["per_class_accuracy"].items():
            value = per_class.get(name)
            if value is None:
                continue
            worst_regression = max(worst_regression, float(base) - float(value))
    fpga_gap = max(float(seed.get("fpga_sim_accuracy_gap", 0.0)) for _, seed in seed_items)

    count = len(macro_f1s)
    return {
        "mean_macro_f1": sum(macro_f1s) / count,
        "worst_seed_macro_f1": min(macro_f1s),
        "worst_domain_macro_f1": min(worst_domain_f1s),
        "mean_accuracy": sum(accuracies) / count,
        "mean_qam_mean_accuracy": sum(qams) / count,
        "worst_class_regression_vs_a0": worst_regression,
        "fpga_sim_accuracy_gap": fpga_gap,
    }


def compute_pilot_gates(
    record: dict,
    a0_baseline: dict,
    pilot_gates: dict,
    minimum_improvement_threshold: float,
) -> dict:
    """Evaluate every pilot hard gate for a trained candidate against same-seed A0."""

    seeds = record["seeds"]
    seed_keys = sorted(str(key) for key in seeds.keys())
    failures: list[dict] = []

    # #7 — no NaN / Inf / missing metric.
    required = ("accuracy", "macro_f1", "qam_mean_accuracy", "fpga_sim_accuracy_gap", "fpga_sim_macro_f1_gap")
    for key in seed_keys:
        seed = seeds[key]
        for field in required:
            if not _is_finite(seed.get(field)):
                failures.append({"gate": "non_finite_or_missing", "seed": key, "detail": f"{field} not finite/missing"})
        per_class = seed.get("per_class_accuracy")
        if not isinstance(per_class, dict):
            failures.append({"gate": "non_finite_or_missing", "seed": key, "detail": "per_class_accuracy missing"})
        else:
            for name in a0_baseline[key]["per_class_accuracy"]:
                if name not in per_class or not _is_finite(per_class.get(name)):
                    failures.append({"gate": "non_finite_or_missing", "seed": key, "detail": f"per_class_accuracy[{name}] not finite/missing"})
        ood_worst = (seed.get("ood", {}) or {}).get("worst_domain_macro_f1")
        if not _is_finite(ood_worst):
            failures.append({"gate": "non_finite_or_missing", "seed": key, "detail": "ood.worst_domain_macro_f1 missing"})

    # #2 — every seed's macro-F1 must not fall below the same-seed A0 macro-F1.
    for key in seed_keys:
        a0_f1 = float(a0_baseline[key]["macro_f1"])
        seed_f1 = float(seeds[key]["macro_f1"])
        if seed_f1 < a0_f1:
            failures.append({"gate": "worst_seed_macro_f1_below_a0", "seed": key, "detail": f"{seed_f1:.6f} < A0 {a0_f1:.6f}"})

    # #3 — per-seed, per-domain OOD macro-F1 must not drop more than the cap
    # below the same-seed, same-domain A0 result.
    for key in seed_keys:
        a0_domains = a0_baseline[key]["domains"]
        seed_domains: dict[str, float] = {}
        for domain_row in (seeds[key].get("ood", {}) or {}).get("domains", []):
            seed_domains[str(domain_row["domain"])] = float(domain_row["macro_f1"])
        for domain, a0_domain in a0_domains.items():
            seed_value = seed_domains.get(domain)
            if seed_value is None:
                failures.append({"gate": "ood_domain_missing", "seed": key, "detail": f"OOD domain {domain} missing"})
            elif seed_value < float(a0_domain["macro_f1"]) - float(pilot_gates["maximum_ood_regression"]):
                failures.append({"gate": "ood_domain_regression", "seed": key, "detail": f"{domain} {seed_value:.6f} < A0 {float(a0_domain['macro_f1']):.6f} - {pilot_gates['maximum_ood_regression']}"})

    # #4 — every seed, every class must not drop more than the per-class cap.
    for key in seed_keys:
        a0_pc = a0_baseline[key]["per_class_accuracy"]
        seed_pc = seeds[key].get("per_class_accuracy", {}) or {}
        for name, a0_value in a0_pc.items():
            value = seed_pc.get(name)
            if value is None:
                continue  # already reported under #7
            if float(value) < float(a0_value) - float(pilot_gates["maximum_per_class_accuracy_drop"]):
                failures.append({"gate": "per_class_accuracy_drop", "seed": key, "detail": f"{name} {float(value):.6f} < A0 {float(a0_value):.6f} - {pilot_gates['maximum_per_class_accuracy_drop']}"})

    # #5 / #6 — FPGA-sim gap floors.
    for key in seed_keys:
        for field in ("fpga_sim_accuracy_gap", "fpga_sim_macro_f1_gap"):
            gap = float(seeds[key].get(field, 0.0))
            limit = float(pilot_gates[f"maximum_{field}"])
            if gap > limit:
                failures.append({"gate": field, "seed": key, "detail": f"{gap:.6f} > {limit}"})

    seed_macro_f1s = [float(seeds[key]["macro_f1"]) for key in seed_keys]
    a0_macro_f1s = [float(a0_baseline[key]["macro_f1"]) for key in seed_keys]
    improvement = sum(seed_macro_f1s) / len(seed_macro_f1s) - sum(a0_macro_f1s) / len(a0_macro_f1s)
    improvement_ok = improvement >= float(minimum_improvement_threshold)

    hard_gates_passed = not failures
    return {
        "improvement_over_a0": improvement,
        "minimum_improvement_threshold": float(minimum_improvement_threshold),
        "improvement_ok": improvement_ok,
        "hard_gates_passed": hard_gates_passed,
        "all_passed": hard_gates_passed and improvement_ok,
        "failures": failures,
    }


def _lexicographic_key(pair: tuple[dict, dict]) -> tuple:
    _, metrics = pair
    return (
        -metrics["mean_macro_f1"],
        -metrics["worst_seed_macro_f1"],
        -metrics["worst_domain_macro_f1"],
        -metrics["mean_accuracy"],
        -metrics["mean_qam_mean_accuracy"],
        metrics["worst_class_regression_vs_a0"],
        metrics["fpga_sim_accuracy_gap"],
        str(pair[0]["variant"]),
    )


def select_candidate(
    summary: dict,
    *,
    minimum_improvement_threshold: float = 0.0,
    pilot_gates: dict | None = None,
) -> dict:
    """Select the Stage-1 winner and apply the pilot hard gates.

    A trained candidate that fails any hard gate (#2-#7) is disqualified from
    promotion; the lexicographic winner is then chosen among A0 plus the
    hard-gate-passing trained candidates.  A hard-gate-passing trained winner is
    only ``promoted`` if it also clears the improvement threshold (#1).
    """

    gates_config = dict(DEFAULT_PILOT_GATES)
    if pilot_gates:
        gates_config.update(pilot_gates)

    a0_baseline = extract_a0_baseline(summary)
    variants = list(summary.get("variants", []))
    if not variants:
        raise RuntimeError("No ablation variants to select from.")

    scored: list[tuple[dict, dict]] = []
    for record in variants:
        metrics = _ranked_metrics(record, a0_baseline)
        if bool(record.get("trained", True)):
            metrics["pilot_gates"] = compute_pilot_gates(
                record, a0_baseline, gates_config, minimum_improvement_threshold
            )
        scored.append((record, metrics))

    gate_report: dict = {}
    for record, metrics in scored:
        if not bool(record.get("trained", True)):
            continue
        gates = metrics["pilot_gates"]
        gate_report[str(record["variant"])] = {
            "hard_gates_passed": gates["hard_gates_passed"],
            "improvement_ok": gates["improvement_ok"],
            "failures": gates["failures"],
        }

    # Hard-gate filter: a trained variant is promotable only if all hard gates
    # (#2-#7) pass.  A0 is always a valid outcome (frozen V2 stays champion).
    eligible = [
        (record, metrics)
        for record, metrics in scored
        if (not bool(record.get("trained", True))) or metrics.get("pilot_gates", {}).get("hard_gates_passed", False)
    ]
    eligible.sort(key=_lexicographic_key)
    winner, metrics = eligible[0]

    winner_trained = bool(winner.get("trained", True))
    improvement = None
    promoted = False
    promotion_blocked_by: str | None = None

    if winner_trained:
        gates = metrics["pilot_gates"]
        improvement = gates["improvement_over_a0"]
        if gates["improvement_ok"]:
            promoted = True
        else:
            promotion_blocked_by = "below_improvement_threshold"
    else:
        # A0 won the ranking.  Distinguish a plain A0 win from a trained candidate
        # that outranked A0 on mean macro-F1 but was disqualified by a hard gate.
        a0_mean = _a0_mean_macro_f1(a0_baseline)
        gate_failed_winner = any(
            bool(record.get("trained", True))
            and not metrics_.get("pilot_gates", {}).get("hard_gates_passed", False)
            and metrics_["mean_macro_f1"] > a0_mean
            for record, metrics_ in scored
        )
        promotion_blocked_by = "pilot_gate_failed" if gate_failed_winner else "a0_won"

    return {
        "selected_variant": str(winner["variant"]),
        "promoted": promoted,
        "winner_trained": winner_trained,
        "promotion_blocked_by": promotion_blocked_by,
        "improvement_over_a0": improvement,
        "minimum_improvement_threshold": float(minimum_improvement_threshold),
        "pilot_gates": gates_config,
        "pilot_gate_report": gate_report,
        "selection_rule": SELECTION_RULE,
        "selection_scope": SELECTION_SCOPE,
        "selection_metrics": metrics,
        "model": dict(winner.get("model", {}) or {}),
        "training": dict(winner.get("training", {}) or {}),
    }


def write_candidate(candidate: dict, out_path: str) -> dict:
    destination = resolve_project_path(out_path)
    write_text_lf(destination, yaml.safe_dump(candidate, sort_keys=False))
    write_text_lf(destination.with_suffix(".json"), json.dumps(candidate, indent=2) + "\n")
    return candidate


def freeze_candidate(
    summary_path: str,
    out_path: str,
    *,
    minimum_improvement_threshold: float = 0.0,
    pilot_gates: dict | None = None,
) -> dict:
    summary_file = resolve_project_path(summary_path)
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    candidate = select_candidate(
        summary,
        minimum_improvement_threshold=minimum_improvement_threshold,
        pilot_gates=pilot_gates,
    )
    candidate["frozen_at_ablation_summary_sha256"] = hashlib.sha256(summary_file.read_bytes()).hexdigest()
    return write_candidate(candidate, out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="outputs/qam_aware_v3_3/ablation/ablation_summary.json")
    parser.add_argument("--out", default="outputs/qam_aware_v3_3/formal/selected_candidate.yaml")
    parser.add_argument("--minimum-improvement-threshold", type=float, default=0.0)
    args = parser.parse_args()
    candidate = freeze_candidate(
        args.summary,
        args.out,
        minimum_improvement_threshold=args.minimum_improvement_threshold,
    )
    print(json.dumps(candidate, indent=2))


if __name__ == "__main__":
    main()
