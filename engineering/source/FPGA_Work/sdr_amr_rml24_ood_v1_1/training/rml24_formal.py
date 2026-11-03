"""24-class formal training with a frozen budget + dedup/resume.

Runs each promoted candidate (from ``pilot_unique_candidates.json``) across the
frozen formal seeds.  The budget is enforced fail-closed:

* default  — exactly 1 candidate x 3 seeds = 3 runs;
* extended — 2 candidates x 3 seeds = 6 runs, only when the select step promoted a
  second candidate with ``--allow-second-candidate``.

Before every ``(candidate, seed)`` run the existing checkpoint's provenance is
verified: a match reuses the verified checkpoint (``REUSED_VERIFIED``), a mismatch
fails closed (``artifact_mismatch``), and duplicate ``(signature, seed)`` pairs are
rejected.  Selection stays validation-only; the test split is never touched here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from contracts.rml24_contract import RML24_MODEL_NAME
from training.rml24_run import run_rml24_trial
from training.rml24_select import apply_candidate
from training.utils import load_yaml, save_json
from v2.candidate_signature import (
    KEY_DATASET_SHA,
    KEY_LABEL_SHA,
    KEY_SPLIT_SHA,
    canonical_candidate_signature,
    config_sha256,
    load_artifact_shas,
)
from v2.results import selection_score

FROZEN_SEEDS = [2026, 2027, 2028]
BUDGET_CAP_RUNS = 6

# The per-seed metrics reported in formal_summary.json and used for mean/std/worst.
_SUMMARY_METRICS = (
    "macro_f1", "rated_0_20_accuracy", "snr_0_accuracy", "min_per_class_accuracy",
)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_formal_runs(candidates: list[dict[str, Any]], seeds: list[int],
                     allow_second_candidate: bool) -> dict[str, Any]:
    """Validate the formal budget and return the plan (fail-closed)."""
    n = len(candidates)
    if n < 1:
        raise RuntimeError("formal requires at least one candidate")
    if n > 2:
        raise RuntimeError(f"formal budget cap exceeded: {n} candidates > 2 ({BUDGET_CAP_RUNS} runs)")
    if len(seeds) != 3:
        raise RuntimeError(f"formal seeds are frozen to 3 ({FROZEN_SEEDS}), got {seeds}")
    total = n * len(seeds)
    if n == 2 and not allow_second_candidate:
        raise RuntimeError(
            "2 candidates require --allow-second-candidate authorization; default budget is "
            "1 candidate x 3 seeds = 3 runs"
        )
    if total > BUDGET_CAP_RUNS:
        raise RuntimeError(f"formal budget {total} runs exceeds cap {BUDGET_CAP_RUNS}")
    return {"unique_candidates": n, "seeds": list(seeds), "total_runs": total}


def verify_provenance(provenance: dict[str, Any], *, expected_signature: str,
                      expected_config_sha: str, expected_dataset_sha: str,
                      expected_split_sha: str) -> list[str]:
    """Return the list of provenance fields that mismatch (empty = verified)."""
    checks = [
        ("candidate_signature", expected_signature),
        ("config_sha256", expected_config_sha),
        ("dataset_sha256", expected_dataset_sha),
        ("split_sha256", expected_split_sha),
    ]
    return [key for key, expected in checks if provenance.get(key) != expected]


def _load_checkpoint_provenance(checkpoint_path: str | Path) -> dict[str, Any]:
    import torch
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    return checkpoint.get("provenance") or {}


def _seed_metrics(result: dict[str, Any]) -> dict[str, float]:
    baseline = (result.get("baseline") or {}).get("metrics") or {}
    return {key: float(baseline.get(key, float("nan"))) for key in _SUMMARY_METRICS}


def _mean_std(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": float("nan"), "std": float("nan")}
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return {"mean": mean, "std": var ** 0.5}


def build_formal_summary(cand_root: Path, signature: str, seeds: list[int]) -> dict[str, Any]:
    """Aggregate per-seed results into mean/std/worst-seed for one candidate."""
    per_seed: dict[str, Any] = {}
    for seed in seeds:
        result_path = cand_root / f"seed{seed}" / "logs" / "result.json"
        best_pt = cand_root / f"seed{seed}" / "checkpoints" / "best.pt"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        per_seed[str(seed)] = {
            "best_epoch": int(result.get("best_epoch", -1)),
            "checkpoint_sha256": _sha256_file(best_pt) if best_pt.is_file() else None,
            "metrics": _seed_metrics(result),
        }
    # worst seed = lowest frozen selection metric (rated_0_20_accuracy).
    worst_seed = min(per_seed, key=lambda s: per_seed[s]["metrics"]["rated_0_20_accuracy"])
    aggregate: dict[str, Any] = {"worst_seed": int(worst_seed), "metrics": {}}
    for metric in _SUMMARY_METRICS:
        aggregate["metrics"][metric] = _mean_std(
            [per_seed[s]["metrics"][metric] for s in per_seed]
        )
    return {"candidate_signature": signature, "per_seed": per_seed, "aggregate": aggregate}


def build_final_manifest(candidate: dict[str, Any], base: dict[str, Any],
                         cand_root: Path, seeds: list[int]) -> dict[str, Any]:
    """Select the best seed and emit the single final-checkpoint manifest (Task I)."""
    selection_metric = "rated_0_20_accuracy"
    best_seed: int | None = None
    best_score = -float("inf")
    for seed in seeds:
        result_path = cand_root / f"seed{seed}" / "logs" / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        score = float(selection_score(result))
        if score > best_score:
            best_score = score
            best_seed = seed
    if best_seed is None:
        raise RuntimeError("no formal seed result found for final manifest")

    checkpoint_path = cand_root / f"seed{best_seed}" / "checkpoints" / "best.pt"
    rml24 = base.get("rml24") or {}
    return {
        "candidate_signature": candidate["candidate_signature"],
        "selected_seed": int(best_seed),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": _sha256_file(checkpoint_path),
        "model_name": rml24.get("model_name", RML24_MODEL_NAME),
        "class_count": 24,
        "label_contract_sha256": base.get(KEY_LABEL_SHA),
        "config_sha256": config_sha256(apply_candidate(base, candidate)),
        "dataset_sha256": base.get(KEY_DATASET_SHA),
        "selection_metric": selection_metric,
        "selection_value": float(best_score),
    }


def run_rml24_formal(config_path: str | Path, search_space_path: str | Path,
                     candidates_path: str | Path, output_root: str | Path | None = None,
                     seeds: list[int] | None = None,
                     ood_domains: list[str] | None = None,
                     artifact_shas: dict[str, str] | None = None,
                     run_trial: Callable[..., dict[str, Any]] = run_rml24_trial) -> dict[str, Any]:
    base = load_yaml(config_path)
    search = load_yaml(search_space_path)
    cfg = search.get("search", {})
    seeds = list(seeds or cfg.get("formal_seeds", FROZEN_SEEDS))
    epochs = int(cfg.get("formal_epochs", base["training"]["epochs"]))

    plan = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
    candidates = plan.get("candidates", [])
    allow_second = bool(plan.get("allow_second_candidate", False))

    budget = plan_formal_runs(candidates, seeds, allow_second)
    print(f"FORMAL_PLAN unique_candidates={budget['unique_candidates']} "
          f"seeds={len(seeds)} total_runs={budget['total_runs']}", flush=True)

    base = dict(base)
    base.update(artifact_shas or load_artifact_shas())

    # Reject duplicate (signature, seed) pairs before any run.
    seen: set[tuple[str, int]] = set()
    for candidate in candidates:
        sig = candidate.get("candidate_signature")
        if sig is None:
            raise RuntimeError(f"candidate {candidate.get('trial')!r} lacks a candidate_signature")
        for seed in seeds:
            pair = (sig, int(seed))
            if pair in seen:
                raise RuntimeError(f"duplicate (signature, seed) pair {pair}")
            seen.add(pair)

    root = Path(output_root or base["output_root"]) / "formal"
    root.mkdir(parents=True, exist_ok=True)

    run_records: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for candidate in candidates:
        name = str(candidate["trial"])
        cand_root = root / name
        cfg_full = apply_candidate(base, candidate)
        expected_signature = canonical_candidate_signature(cfg_full)
        expected_config_sha = config_sha256(cfg_full)
        expected_dataset_sha = base[KEY_DATASET_SHA]
        expected_split_sha = base[KEY_SPLIT_SHA]
        if expected_signature != candidate.get("candidate_signature"):
            raise RuntimeError(
                f"candidate {name!r} signature drift: plan={candidate.get('candidate_signature')} "
                f"recomputed={expected_signature}"
            )

        for seed in seeds:
            seed_root = cand_root / f"seed{seed}"
            best_pt = seed_root / "checkpoints" / "best.pt"
            result_json = seed_root / "logs" / "result.json"

            if best_pt.is_file() and result_json.is_file():
                provenance = _load_checkpoint_provenance(best_pt)
                mismatches = verify_provenance(
                    provenance, expected_signature=expected_signature,
                    expected_config_sha=expected_config_sha,
                    expected_dataset_sha=expected_dataset_sha,
                    expected_split_sha=expected_split_sha,
                )
                if mismatches:
                    raise RuntimeError(
                        f"FORMAL_RUN result=FAIL reason=artifact_mismatch candidate={name} "
                        f"seed={seed} mismatches={mismatches}"
                    )
                run_records.append({"candidate": name, "candidate_signature": expected_signature,
                                    "seed": seed, "status": "REUSED_VERIFIED"})
                print(f"FORMAL_RUN candidate={name} seed={seed} status=REUSED_VERIFIED", flush=True)
                continue

            run_trial(cfg_full, f"seed{seed}", cand_root, seed=seed, epochs=epochs,
                      eval_baseline=True, eval_fake_int8=True, eval_channel_ood=True,
                      ood_domains=ood_domains)
            # Self-check the freshly produced checkpoint provenance.
            provenance = _load_checkpoint_provenance(best_pt)
            mismatches = verify_provenance(
                provenance, expected_signature=expected_signature,
                expected_config_sha=expected_config_sha,
                expected_dataset_sha=expected_dataset_sha,
                expected_split_sha=expected_split_sha,
            )
            if mismatches:
                raise RuntimeError(
                    f"FORMAL_RUN result=FAIL reason=artifact_mismatch candidate={name} "
                    f"seed={seed} mismatches={mismatches}"
                )
            run_records.append({"candidate": name, "candidate_signature": expected_signature,
                                "seed": seed, "status": "TRAINED"})
            print(f"FORMAL_RUN candidate={name} seed={seed} status=TRAINED", flush=True)

        summaries[name] = build_formal_summary(cand_root, expected_signature, seeds)

    save_json({"seeds": seeds, "epochs": epochs, "budget": budget,
               "runs": run_records, "candidates": summaries},
              root / "formal_summary.json")

    final_manifest = build_final_manifest(candidates[0], base, root / str(candidates[0]["trial"]),
                                          seeds)
    save_json(final_manifest, root / "final_checkpoint_manifest.json")

    return {"output_root": str(root), "n_candidates": len(candidates), "seeds": seeds,
            "runs": run_records, "final_checkpoint_manifest": final_manifest}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--search-space", default="configs/search_space_rml24.yaml")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    args = parser.parse_args()
    print(run_rml24_formal(args.config, args.search_space, args.candidates,
                           args.output_root, args.seeds))


if __name__ == "__main__":
    main()
