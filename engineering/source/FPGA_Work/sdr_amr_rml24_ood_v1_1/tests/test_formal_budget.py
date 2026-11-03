"""V1.1 budget/dedup — formal budget, resume/dedup, summary and final manifest.

Offline these tests exercise the pure formal logic and the orchestration with a
fake ``run_trial`` (no GPU, no training): the default budget must be exactly
1 candidate x 3 seeds = 3 runs, a second candidate requires explicit
authorization, a checkpoint with matching provenance is reused (REUSED_VERIFIED)
while a mismatch fails closed (artifact_mismatch), and duplicate
(signature, seed) pairs are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.rml24_contract import CODE_VERSION, LABEL_ORDER_24
from training.rml24_formal import (
    build_final_manifest,
    build_formal_summary,
    plan_formal_runs,
    run_rml24_formal,
    verify_provenance,
)
from training.rml24_select import apply_candidate
from v2.candidate_signature import (
    KEY_DATASET_SHA,
    KEY_LABEL_SHA,
    KEY_SPLIT_SHA,
    build_checkpoint_provenance,
    canonical_candidate_signature,
    config_sha256,
    label_contract_sha256,
)

_DS = "a" * 64
_SPLIT = "b" * 64
_SHA = {KEY_DATASET_SHA: _DS, KEY_SPLIT_SHA: _SPLIT, KEY_LABEL_SHA: label_contract_sha256()}
SEEDS = [2026, 2027, 2028]


def _cand(sig: str = "s" * 64, trial: str = "t000") -> dict:
    return {"trial": trial, "candidate_signature": sig, "selection_score": 0.9,
            "v2": {}, "training": {}}


# --------------------------------------------------------------------------- #
# plan_formal_runs
# --------------------------------------------------------------------------- #
def test_plan_default_one_candidate() -> None:
    plan = plan_formal_runs([_cand()], SEEDS, allow_second_candidate=False)
    assert plan == {"unique_candidates": 1, "seeds": SEEDS, "total_runs": 3}


def test_plan_second_candidate_requires_authorization() -> None:
    with pytest.raises(RuntimeError):
        plan_formal_runs([_cand("a" * 64, "t1"), _cand("b" * 64, "t2")], SEEDS, False)
    plan = plan_formal_runs([_cand("a" * 64, "t1"), _cand("b" * 64, "t2")], SEEDS, True)
    assert plan["total_runs"] == 6


def test_plan_budget_cap_exceeded() -> None:
    with pytest.raises(RuntimeError):
        plan_formal_runs([_cand("a" * 64), _cand("b" * 64), _cand("c" * 64)], SEEDS, True)


def test_plan_requires_three_seeds() -> None:
    with pytest.raises(RuntimeError):
        plan_formal_runs([_cand()], [2026, 2027], False)


# --------------------------------------------------------------------------- #
# verify_provenance
# --------------------------------------------------------------------------- #
def _prov(sig: str = "s" * 64, cfg: str = "c" * 64) -> dict:
    return {"candidate_signature": sig, "config_sha256": cfg,
            "dataset_sha256": _DS, "split_sha256": _SPLIT}


def test_verify_provenance_clean() -> None:
    assert verify_provenance(_prov(), expected_signature="s" * 64, expected_config_sha="c" * 64,
                             expected_dataset_sha=_DS, expected_split_sha=_SPLIT) == []


def test_verify_provenance_reports_each_mismatch() -> None:
    bad = _prov(sig="x" * 64, cfg="y" * 64)
    bad["dataset_sha256"] = "z" * 64
    mismatches = verify_provenance(bad, expected_signature="s" * 64, expected_config_sha="c" * 64,
                                   expected_dataset_sha=_DS, expected_split_sha=_SPLIT)
    assert set(mismatches) == {"candidate_signature", "config_sha256", "dataset_sha256"}


# --------------------------------------------------------------------------- #
# build_formal_summary
# --------------------------------------------------------------------------- #
def _write_seed(cand_root: Path, seed: int, rated: float, *, macro: float = 0.88,
                snr0: float = 0.70, min_cls: float = 0.50, epoch: int = 3) -> None:
    seed_root = cand_root / f"seed{seed}"
    (seed_root / "checkpoints").mkdir(parents=True, exist_ok=True)
    (seed_root / "logs").mkdir(parents=True, exist_ok=True)
    (seed_root / "checkpoints" / "best.pt").write_bytes(b"checkpoint-bytes")
    result = {"trial": f"seed{seed}", "seed": seed, "best_epoch": epoch,
              "baseline": {"metrics": {
                  "macro_f1": macro, "rated_0_20_accuracy": rated,
                  "snr_0_accuracy": snr0, "min_per_class_accuracy": min_cls}}}
    (seed_root / "logs" / "result.json").write_text(json.dumps(result), encoding="utf-8")


def test_build_formal_summary_mean_std_and_worst_seed(tmp_path: Path) -> None:
    cand_root = tmp_path / "cand"
    _write_seed(cand_root, 2026, 0.90, epoch=3)
    _write_seed(cand_root, 2027, 0.92, epoch=5)
    _write_seed(cand_root, 2028, 0.88, epoch=4)
    summary = build_formal_summary(cand_root, "s" * 64, SEEDS)
    assert summary["candidate_signature"] == "s" * 64
    assert summary["aggregate"]["worst_seed"] == 2028  # lowest rated_0_20_accuracy
    rated = summary["aggregate"]["metrics"]["rated_0_20_accuracy"]
    assert abs(rated["mean"] - 0.90) < 1e-9
    assert abs(rated["std"] - ((0.0 ** 2 + 0.02 ** 2 + (-0.02) ** 2) / 3) ** 0.5) < 1e-9
    assert summary["per_seed"]["2026"]["best_epoch"] == 3
    # SHA of the deterministic 15-byte file.
    assert summary["per_seed"]["2026"]["checkpoint_sha256"] is not None


# --------------------------------------------------------------------------- #
# build_final_manifest
# --------------------------------------------------------------------------- #
_BASE_TRAINING = {
    "epochs": 80, "learning_rate": 1e-3, "weight_decay": 1e-4, "batch_size": 256,
    "scheduler_factor": 0.5, "scheduler_patience": 5, "minimum_lr": 1e-6,
    "amp": True, "amp_dtype": "bfloat16", "gradient_clip_norm": 2.0,
    "reconstruction_weight": 0.0, "snr_weighting": {}, "minimum_epochs_before_stopping": 30,
}
_BASE_V2 = {"loss": "focal", "focal_gamma": 2.0, "optimizer": "adamw",
            "class_sampling": "balanced", "sgd_momentum": 0.9}


def _base_with_shas() -> dict:
    return {
        "model": {"denoiser_channels": 24},
        "rml24": {"model_name": "RML2018_24_BENCHMARK", "apply_channel_augmentation": False},
        "v2": dict(_BASE_V2),
        "training": dict(_BASE_TRAINING),
        **_SHA,
    }


def test_build_final_manifest_selects_best_seed(tmp_path: Path) -> None:
    cand_root = tmp_path / "cand"
    _write_seed(cand_root, 2026, 0.90, epoch=3)
    _write_seed(cand_root, 2027, 0.93, epoch=5)
    _write_seed(cand_root, 2028, 0.88, epoch=4)
    base = _base_with_shas()
    full = {"trial": "t000", "v2": dict(_BASE_V2), "training": {"learning_rate": 1e-3}}
    candidate = {"trial": "t000", "v2": dict(_BASE_V2), "training": {"learning_rate": 1e-3},
                 "candidate_signature": canonical_candidate_signature(apply_candidate(base, full))}
    manifest = build_final_manifest(candidate, base, cand_root, SEEDS)
    assert manifest["selected_seed"] == 2027
    assert manifest["selection_metric"] == "rated_0_20_accuracy"
    assert abs(manifest["selection_value"] - 0.93) < 1e-9
    assert manifest["class_count"] == 24
    assert manifest["model_name"] == "RML2018_24_BENCHMARK"
    assert manifest["dataset_sha256"] == _DS
    assert manifest["label_contract_sha256"] == label_contract_sha256()
    assert len(manifest["checkpoint_sha256"]) == 64


# --------------------------------------------------------------------------- #
# run_rml24_formal orchestration (fake run_trial, no training)
# --------------------------------------------------------------------------- #
def _write_yaml(path: Path, data: dict) -> None:
    import yaml
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _fake_run_trial(config, trial_name, output_root, seed, epochs, **kwargs):
    import torch
    seed_root = Path(output_root) / trial_name
    (seed_root / "checkpoints").mkdir(parents=True, exist_ok=True)
    (seed_root / "logs").mkdir(parents=True, exist_ok=True)
    provenance = build_checkpoint_provenance(config, CODE_VERSION)
    torch.save({"provenance": provenance, "model_state": {},
                "class_names": list(LABEL_ORDER_24)},
               seed_root / "checkpoints" / "best.pt")
    rated = 0.90 + 0.0001 * seed
    result = {"trial": trial_name, "seed": seed, "best_epoch": 3,
              "baseline": {"metrics": {
                  "macro_f1": 0.88, "rated_0_20_accuracy": rated,
                  "snr_0_accuracy": 0.70, "min_per_class_accuracy": 0.50,
                  "per_class_accuracy": [0.9] * 24}},
              "training": dict(config["training"]), "v2": dict(config.get("v2", {}))}
    (seed_root / "logs" / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return result


def _make_plan_files(tmp_path: Path, candidates: list[dict], *,
                     allow_second: bool = False) -> tuple[Path, Path, Path]:
    base_no_shas = {
        "model": {"denoiser_channels": 24},
        "rml24": {"model_name": "RML2018_24_BENCHMARK", "apply_channel_augmentation": False},
        "v2": dict(_BASE_V2),
        "training": dict(_BASE_TRAINING),
    }
    config_path = tmp_path / "base.yaml"
    search_path = tmp_path / "search.yaml"
    candidates_path = tmp_path / "candidates.json"
    _write_yaml(config_path, base_no_shas)
    _write_yaml(search_path, {"search": {"pilot_seed": 2026, "formal_seeds": SEEDS,
                                         "formal_epochs": 80,
                                         "prune": {"top_candidates": 1}}})
    candidates_path.write_text(json.dumps({"candidates": candidates,
                                           "allow_second_candidate": allow_second}),
                               encoding="utf-8")
    return config_path, search_path, candidates_path


def _one_candidate(sig: str) -> dict:
    return {"trial": "t000", "v2": dict(_BASE_V2), "training": {"learning_rate": 1e-3},
            "selection_score": 0.9, "candidate_signature": sig}


def test_run_formal_trains_and_writes_manifests(tmp_path: Path) -> None:
    base = _base_with_shas()
    candidate = _one_candidate(canonical_candidate_signature(apply_candidate(base, _one_candidate(""))))
    config_path, search_path, candidates_path = _make_plan_files(tmp_path, [candidate])
    out = run_rml24_formal(config_path, search_path, candidates_path,
                           output_root=tmp_path / "runs", artifact_shas=_SHA,
                           run_trial=_fake_run_trial)
    assert out["n_candidates"] == 1
    assert [r["status"] for r in out["runs"]] == ["TRAINED"] * 3

    root = tmp_path / "runs" / "formal"
    summary = json.loads((root / "formal_summary.json").read_text(encoding="utf-8"))
    assert summary["budget"]["total_runs"] == 3
    assert len(summary["runs"]) == 3

    manifest = json.loads((root / "final_checkpoint_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_signature"] == candidate["candidate_signature"]
    assert manifest["class_count"] == 24
    assert manifest["selection_metric"] == "rated_0_20_accuracy"
    assert manifest["selected_seed"] in SEEDS


def test_run_formal_reuses_verified_checkpoint(tmp_path: Path) -> None:
    base = _base_with_shas()
    candidate = _one_candidate(canonical_candidate_signature(apply_candidate(base, _one_candidate(""))))
    config_path, search_path, candidates_path = _make_plan_files(tmp_path, [candidate])
    run_rml24_formal(config_path, search_path, candidates_path,
                     output_root=tmp_path / "runs", artifact_shas=_SHA,
                     run_trial=_fake_run_trial)
    # Second invocation with identical candidates must reuse, not retrain.
    out = run_rml24_formal(config_path, search_path, candidates_path,
                           output_root=tmp_path / "runs", artifact_shas=_SHA,
                           run_trial=_fake_run_trial)
    assert [r["status"] for r in out["runs"]] == ["REUSED_VERIFIED"] * 3


def test_run_formal_artifact_mismatch_fails_closed(tmp_path: Path) -> None:
    import torch
    base = _base_with_shas()
    candidate = _one_candidate(canonical_candidate_signature(apply_candidate(base, _one_candidate(""))))
    config_path, search_path, candidates_path = _make_plan_files(tmp_path, [candidate])
    # Pre-seed a checkpoint with WRONG dataset provenance.
    seed_root = tmp_path / "runs" / "formal" / "t000" / "seed2026"
    (seed_root / "checkpoints").mkdir(parents=True, exist_ok=True)
    (seed_root / "logs").mkdir(parents=True, exist_ok=True)
    bad = build_checkpoint_provenance(base, CODE_VERSION)
    bad["dataset_sha256"] = "z" * 64
    torch.save({"provenance": bad, "model_state": {}, "class_names": list(LABEL_ORDER_24)},
               seed_root / "checkpoints" / "best.pt")
    (seed_root / "logs" / "result.json").write_text(
        json.dumps({"trial": "seed2026", "seed": 2026, "best_epoch": 1,
                    "baseline": {"metrics": {"rated_0_20_accuracy": 0.9}}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="artifact_mismatch"):
        run_rml24_formal(config_path, search_path, candidates_path,
                         output_root=tmp_path / "runs", artifact_shas=_SHA,
                         run_trial=_fake_run_trial)


def test_run_formal_duplicate_signature_seed_rejected(tmp_path: Path) -> None:
    base = _base_with_shas()
    sig = canonical_candidate_signature(apply_candidate(base, _one_candidate("")))
    candidates = [_one_candidate(sig), {**_one_candidate(sig), "trial": "t001"}]
    config_path, search_path, candidates_path = _make_plan_files(
        tmp_path, candidates, allow_second=True)
    with pytest.raises(RuntimeError, match="duplicate"):
        run_rml24_formal(config_path, search_path, candidates_path,
                         output_root=tmp_path / "runs", artifact_shas=_SHA,
                         run_trial=_fake_run_trial)


def test_run_formal_budget_cap_fails_closed(tmp_path: Path) -> None:
    candidates = [_cand("a" * 64, "t0"), _cand("b" * 64, "t1"), _cand("c" * 64, "t2")]
    config_path, search_path, candidates_path = _make_plan_files(
        tmp_path, candidates, allow_second=True)
    with pytest.raises(RuntimeError, match="cap"):
        run_rml24_formal(config_path, search_path, candidates_path,
                         output_root=tmp_path / "runs", artifact_shas=_SHA,
                         run_trial=_fake_run_trial)
