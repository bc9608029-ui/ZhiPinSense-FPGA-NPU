"""Reassess existing RML24 pilot checkpoints on a single unified validation index set.

The pilot-trial ``rated_0_20_accuracy`` was, before the caliber fix, computed on an
OOK-only *prefix* of the label-major validation split (see
``docs/RML24_PILOT_METRIC_AUDIT.md``), so every historical ``result.json`` carries a
saturated, single-class, wrong ``rated_0_20``.  This tool recomputes the metrics for
every trial's saved ``best.pt`` **from scratch** on the frozen validation split and
therefore must never read the old ``baseline`` / ``history`` metrics.

Guarantees (all enforced here, not merely documented):

* **validation-only** — the tool builds ``RadioML2018Dataset(split="validation")`` and
  never constructs a test split; ``final_blind_test_accessed`` is hard-coded ``False``.
* **same indices for every trial** — the unified index set is computed exactly once
  (full split when ``samples=None``, else a deterministic stratified subset with a
  fixed seed), and every checkpoint is scored on that identical subset.
* **no retraining / no checkpoint mutation** — checkpoints are opened read-only via
  ``torch.load``; nothing is written under the pilot root.
* **no old metric reads** — the only fields read from each ``result.json`` are the
  whitelisted identity/geometry keys (``trial``/``seed``/``v2``/``training``/model
  name); ``baseline``/``history``/``best_selection_score`` are never touched.

Outputs (under ``<pilot_root>/../reassess/`` unless ``--output-dir`` is given):

* ``reassessed_pilot_ranking.json`` — coverage + per-trial fresh metrics + ranking +
  duplicate report + the documented multi-metric sort rule;
* ``reassessed_formal_candidate_plan.json`` — the promoted candidate(s) in the shape
  ``run_rml24_formal`` consumes (``candidates`` / ``allow_second_candidate``);
* ``reassessed_pilot_ranking.csv`` — a deterministic, human-readable ranking table.

The final sort rule is **not** a single saturated value.  It is a descending
lexicographic key: ``(round(rated_0_20_accuracy * 1e4), min_per_class_accuracy,
snr_0_accuracy, macro_f1, accuracy)``.  Quantising the primary metric to ``1e-4`` lets
near-tied (saturated) ``rated_0_20`` values fall through to ``min_per_class_accuracy``,
``snr_0_accuracy`` and ``macro_f1``, so the ranking stays meaningful even when the
primary metric saturates.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

from contracts.rml24_contract import LABEL_ORDER_24
from datasets.ad_amr_dataset import collate_ad_amr
from datasets.radioml2018_dataset import RadioML2018Dataset
from evaluation.evaluate_rml24 import _load_model, _stratified_indices
from training.ad_amr_v1_1_trainer import _summary
from training.rml24_select import apply_candidate
from training.utils import load_yaml, save_json, select_device
from v2.candidate_signature import canonical_candidate_signature, load_artifact_shas

# The frozen split seed is the natural source for any deterministic re-subsampling of
# the validation split (it is the seed that produced the audited train/val/test index).
REASSESS_INDEX_SEED = 20261003

# Primary-metric granularity for the sort key (see module docstring).  A value of
# 1e-4 means two ``rated_0_20_accuracy`` values within ~5e-5 are treated as tied and
# ordered by the secondary metrics instead.
_RANK_GRANULARITY = 1e-4

# Only these identity/geometry fields are read from a result.json.  Anything else —
# especially ``baseline`` / ``history`` / ``best_selection_score`` — is never read.
_META_WHITELIST = ("trial", "seed", "v2", "training", "model_name", "classes")


def _metric_vector(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "accuracy": float(metrics["accuracy"]),
        "macro_f1": float(metrics["macro_f1"]),
        "rated_0_20_accuracy": float(metrics["rated_0_20_accuracy"]),
        "snr_0_accuracy": float(metrics["snr_0_accuracy"]),
        "min_per_class_accuracy": float(metrics["min_per_class_accuracy"]),
    }


def _rank_key(metrics: dict[str, float]) -> tuple[Any, ...]:
    """Documented multi-metric sort key (all descending)."""
    return (
        int(round(float(metrics["rated_0_20_accuracy"]) / _RANK_GRANULARITY)),
        float(metrics["min_per_class_accuracy"]),
        float(metrics["snr_0_accuracy"]),
        float(metrics["macro_f1"]),
        float(metrics["accuracy"]),
    )


SORT_RULE = (
    "descending lexicographic key = (round(rated_0_20_accuracy / 1e-4), "
    "min_per_class_accuracy, snr_0_accuracy, macro_f1, accuracy); the primary metric is "
    "quantised to 1e-4 so near-tied (saturated) rated_0_20 values fall through to "
    "min_per_class_accuracy / snr_0_accuracy / macro_f1"
)


def _build_unified_indices(config: dict[str, Any], samples: int | None,
                           index_seed: int) -> tuple[RadioML2018Dataset, list[int]]:
    """Build the frozen validation dataset and the *single* index set shared by all trials."""
    public = config["public_data"]
    dataset = RadioML2018Dataset(
        public["hdf5_path"], public["classes_path"], public["audit_path"],
        public["index_path"], "validation",
    )
    if samples is None:
        indices = list(range(len(dataset)))
    else:
        limit = int(samples)
        if limit >= len(dataset):
            indices = list(range(len(dataset)))
        else:
            indices = _stratified_indices(
                np.asarray(dataset.labels, dtype=np.int64),
                np.asarray(dataset.snrs, dtype=np.float32),
                limit,
                index_seed,
            )
    return dataset, indices


def _coverage(dataset: RadioML2018Dataset, indices: list[int]) -> dict[str, Any]:
    labels = np.asarray(dataset.labels, dtype=np.int64)[indices]
    snrs = np.asarray(dataset.snrs, dtype=np.float32)[indices]
    return {
        "samples": int(len(indices)),
        "n_classes_covered": int(len(set(labels.tolist()))),
        "n_snr_covered": int(len(set(float(v) for v in snrs.tolist()))),
        "classes_covered": sorted(set(labels.tolist())),
        "snrs_covered": sorted(set(float(v) for v in snrs.tolist())),
    }


def _discover_trials(pilot_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Discover each trial's ``best.pt`` and its sibling ``logs/result.json`` metadata."""
    if not pilot_root.is_dir():
        raise FileNotFoundError(f"pilot root missing: {pilot_root}")
    ok: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for best_pt in sorted(pilot_root.rglob("best.pt")):
        resolved = best_pt.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        trial_dir = best_pt.parent.parent
        result_json = trial_dir / "logs" / "result.json"
        if not result_json.is_file():
            orphans.append({"best_pt": str(best_pt)})
            continue
        meta = json.loads(result_json.read_text(encoding="utf-8"))
        ok.append({"best_pt": best_pt, "result_json": result_json, "meta": meta})
    return ok, orphans


def _extract_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Read only the whitelisted identity/geometry fields (never baseline/history)."""
    trial = meta.get("trial")
    seed = meta.get("seed")
    v2 = meta.get("v2") or {}
    training = meta.get("training") or {}
    if not isinstance(v2, dict) or not isinstance(training, dict):
        raise RuntimeError(f"trial {trial!r}: result.json lacks dict v2/training metadata")
    return {"trial": trial, "seed": seed, "v2": dict(v2), "training": dict(training)}


def _evaluate_on_indices(model: torch.nn.Module, device: torch.device,
                         dataset: RadioML2018Dataset, indices: list[int],
                         batch_size: int) -> dict[str, Any]:
    subset = Subset(dataset, indices)
    loader = DataLoader(subset, batch_size=batch_size, shuffle=False, num_workers=0,
                        collate_fn=collate_ad_amr, pin_memory=device.type == "cuda")
    targets: list[int] = []
    predictions: list[int] = []
    snrs: list[float] = []
    with torch.inference_mode():
        for batch in loader:
            out, _ = model(batch["noisy_iq"].to(device, non_blocking=True))
            if not bool(torch.isfinite(out).all()):
                raise RuntimeError("non-finite 24-class logits during reassessment")
            targets.extend(batch["label"].tolist())
            predictions.extend(out.argmax(1).cpu().tolist())
            snrs.extend(float(v) for v in batch["snr_db"].tolist())
    return _summary(targets, predictions, snrs, len(LABEL_ORDER_24))


def run_reassess(config_path: str | Path, search_space_path: str | Path,
                 pilot_root: str | Path, eval_samples: int | None = None,
                 index_seed: int = REASSESS_INDEX_SEED,
                 output_dir: str | Path | None = None) -> dict[str, Any]:
    base = load_yaml(config_path)
    search = load_yaml(search_space_path)
    cfg = search.get("search", {})

    base = dict(base)
    base.update(load_artifact_shas())

    pilot_root = Path(pilot_root)
    device = select_device(str(base.get("device", "auto")))
    batch_size = int(base["evaluation"]["batch_size"])

    dataset, indices = _build_unified_indices(base, eval_samples, index_seed)
    coverage = _coverage(dataset, indices)

    ok, orphans = _discover_trials(pilot_root)
    if not ok:
        report: dict[str, Any] = {
            "result": "FAIL",
            "reason": "no pilot best.pt with a sibling logs/result.json discovered",
            "pilot_root": str(pilot_root),
            "split": "validation",
            "final_blind_test_accessed": False,
        }
        _emit(report, pilot_root, output_dir)
        return report

    results: list[dict[str, Any]] = []
    for entry in ok:
        meta = _extract_metadata(entry["meta"])
        model, checkpoint = _load_model(base, entry["best_pt"], fake_int8=False, device=device)
        try:
            metrics = _evaluate_on_indices(model, device, dataset, indices, batch_size)
        finally:
            del model
            if device.type == "cuda":
                torch.cuda.empty_cache()
        signature = canonical_candidate_signature(
            apply_candidate(base, {"v2": meta["v2"], "training": meta["training"]})
        )
        results.append({
            "trial": meta["trial"],
            "seed": meta["seed"],
            "checkpoint": str(entry["best_pt"]),
            "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
            "candidate_signature": signature,
            "v2": meta["v2"],
            "training": meta["training"],
            "metrics": _metric_vector(metrics),
        })

    # Fail closed on any non-finite fresh metric (a real model/data problem, never pruned).
    for result in results:
        for name, value in result["metrics"].items():
            if not math.isfinite(value):
                report = {
                    "result": "FAIL",
                    "reason": f"trial {result['trial']!r} has non-finite {name}={value!r}",
                    "pilot_root": str(pilot_root),
                    "split": "validation",
                    "final_blind_test_accessed": False,
                }
                _emit(report, pilot_root, output_dir)
                return report

    # Dedupe by canonical candidate signature, keeping the best trial per signature.
    groups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        groups.setdefault(result["candidate_signature"], []).append(result)
    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for signature, group in groups.items():
        group = sorted(group, key=lambda r: _rank_key(r["metrics"]), reverse=True)
        best = group[0]
        unique.append(best)
        if len(group) > 1:
            duplicates.append({
                "candidate_signature": signature,
                "kept_trial": best["trial"],
                "duplicate_trials": [r["trial"] for r in group[1:]],
            })

    ranked = sorted(unique, key=lambda r: _rank_key(r["metrics"]), reverse=True)
    seeds = list(cfg.get("formal_seeds", [2026, 2027, 2028]))
    n_top = int(cfg.get("prune", {}).get("top_candidates", 1))
    if n_top > len(ranked):
        n_top = len(ranked)

    promoted = ranked[:n_top]
    candidates = [
        {
            "trial": r["trial"],
            "candidate_signature": r["candidate_signature"],
            "selection_score": float(r["metrics"]["rated_0_20_accuracy"]),
            "v2": r["v2"],
            "training": r["training"],
            "reassessed_metrics": r["metrics"],
        }
        for r in promoted
    ]

    full_class_coverage = coverage["n_classes_covered"] == len(LABEL_ORDER_24)
    full_snr_coverage = coverage["n_snr_covered"] == 26
    status = "PASS" if full_class_coverage and full_snr_coverage else "FAIL"
    reason = (
        "coverage OK"
        if status == "PASS"
        else f"incomplete validation coverage: classes={coverage['n_classes_covered']}/24 "
             f"snrs={coverage['n_snr_covered']}/26"
    )

    ranking = [
        {
            "rank": position,
            "trial": r["trial"],
            "seed": r["seed"],
            "checkpoint": r["checkpoint"],
            "checkpoint_epoch": r["checkpoint_epoch"],
            "candidate_signature": r["candidate_signature"],
            "metrics": r["metrics"],
        }
        for position, r in enumerate(ranked, start=1)
    ]

    report = {
        "result": status,
        "reason": reason,
        "pilot_root": str(pilot_root),
        "split": "validation",
        "eval_samples": eval_samples,
        "index_seed": index_seed,
        "final_blind_test_accessed": False,
        "coverage": coverage,
        "sort_rule": SORT_RULE,
        "n_trials_discovered": len(ok),
        "n_orphan_checkpoints": len(orphans),
        "n_unique": len(unique),
        "ranking": ranking,
        "duplicates": duplicates,
        "formal_candidate_plan": {
            "formal_seeds": seeds,
            "top_candidates": n_top,
            "budget": {
                "unique_candidates": len(candidates),
                "seeds": seeds,
                "total_runs": len(candidates) * len(seeds),
            },
            "candidates": candidates,
        },
    }

    formal_plan = {
        "candidates": [
            {
                "trial": c["trial"],
                "candidate_signature": c["candidate_signature"],
                "v2": c["v2"],
                "training": c["training"],
            }
            for c in candidates
        ],
        "allow_second_candidate": bool(n_top >= 2),
        "reassess_source": "reassessed_pilot_ranking.json",
        "sort_rule": SORT_RULE,
    }

    _emit(report, pilot_root, output_dir, formal_plan=formal_plan, ranked=ranked)
    return report


def _emit(report: dict[str, Any], pilot_root: Path, output_dir: str | Path | None,
          *, formal_plan: dict[str, Any] | None = None,
          ranked: list[dict[str, Any]] | None = None) -> None:
    destination = Path(output_dir) if output_dir else (pilot_root.parent / "reassess")
    destination.mkdir(parents=True, exist_ok=True)
    save_json(report, destination / "reassessed_pilot_ranking.json")
    if formal_plan is not None:
        save_json(formal_plan, destination / "reassessed_formal_candidate_plan.json")
    if ranked is not None:
        header = ["rank", "trial", "seed", "rated_0_20_accuracy", "accuracy",
                  "macro_f1", "snr_0_accuracy", "min_per_class_accuracy",
                  "candidate_signature"]
        rows = [header]
        for position, r in enumerate(ranked, start=1):
            m = r["metrics"]
            rows.append([
                str(position), str(r["trial"]), str(r["seed"]),
                f"{m['rated_0_20_accuracy']:.6f}", f"{m['accuracy']:.6f}",
                f"{m['macro_f1']:.6f}", f"{m['snr_0_accuracy']:.6f}",
                f"{m['min_per_class_accuracy']:.6f}", str(r["candidate_signature"]),
            ])
        (destination / "reassessed_pilot_ranking.csv").write_text(
            "\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8"
        )
    report["_output_dir"] = str(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--search-space", default="configs/search_space_rml24.yaml")
    parser.add_argument("--pilot-root", required=True)
    parser.add_argument("--eval-samples", type=int, default=None)
    parser.add_argument("--index-seed", type=int, default=REASSESS_INDEX_SEED)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    try:
        report = run_reassess(args.config, args.search_space, args.pilot_root,
                              args.eval_samples, args.index_seed, args.output_dir)
    except Exception as exc:  # fail-closed: always emit exactly one result line
        print(f"RML24_PILOT_REASSESS result=FAIL reason={exc}", flush=True)
        sys.exit(1)
    print(f"RML24_PILOT_REASSESS result={report['result']}", flush=True)
    sys.exit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()
