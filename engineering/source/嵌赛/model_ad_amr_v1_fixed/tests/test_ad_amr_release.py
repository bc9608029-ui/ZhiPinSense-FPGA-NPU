"""Release-blocking regressions for device paths and V2-relative promotion."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from evaluation.evaluate_ad_amr import evaluate
from evaluation.evaluate_ad_amr_pilot import evaluate_paired
from models.ad_amr_net import build_ad_amr_model, profile_ad_amr_model
from scripts.run_pilot import decide_gates
from training.train_ad_amr import run_training
from training.utils import load_yaml


def _metric_record(seed: int, candidate_gain: float) -> dict:
    classes = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    baseline = {
        "accuracy": 0.70, "macro_f1": 0.69, "qam_mean_accuracy": 0.46,
        "accuracy_0_10db": 0.75,
        "per_class_accuracy": {name: 0.65 for name in classes},
        "per_snr_accuracy": {"0": 0.80, "10": 0.90, "20": 0.93},
    }
    candidate = {
        "accuracy": baseline["accuracy"] + candidate_gain,
        "macro_f1": baseline["macro_f1"] + candidate_gain,
        "qam_mean_accuracy": baseline["qam_mean_accuracy"] + candidate_gain,
        "accuracy_0_10db": baseline["accuracy_0_10db"] + candidate_gain,
        "per_class_accuracy": {name: value + candidate_gain for name, value in baseline["per_class_accuracy"].items()},
        "per_snr_accuracy": {name: value + candidate_gain for name, value in baseline["per_snr_accuracy"].items()},
    }
    return {
        "seed": seed,
        "paired": {"candidate": candidate, "v2": baseline, "final_blind_test_accessed": False},
        "ood": {"cfo": {"candidate": {"macro_f1": 0.60 + candidate_gain},
                          "v2": {"macro_f1": 0.60}}},
    }


def _thresholds() -> dict[str, float]:
    return {
        "mean_macro_f1_gain": 0.01,
        "mean_accuracy_gain": 0.01,
        "per_seed_macro_f1_regression": 0.0,
        "per_class_regression": 0.03,
        "snr_0_10_20_regression": 0.01,
        "accuracy_0_10db_gain": 0.02,
        "qam_mean_regression": 0.0,
        "ood_domain_macro_f1_regression": 0.01,
    }


def test_pilot_cannot_promote_chance_or_v2_regression() -> None:
    weak = [_metric_record(2026, -0.20), _metric_record(2027, -0.20)]
    gates = decide_gates(weak, _thresholds(), training_complete=True, onnx_ok=True)
    assert not all(gate["pass"] for gate in gates)
    assert not next(g for g in gates if g["name"] == "mean_macro_f1_gain")["pass"]


def test_pilot_promotes_only_when_every_contract_passes() -> None:
    strong = [_metric_record(2026, 0.03), _metric_record(2027, 0.03)]
    gates = decide_gates(strong, _thresholds(), training_complete=True, onnx_ok=True)
    assert all(gate["pass"] for gate in gates), gates


def test_paired_evaluator_rejects_test_and_blind_namespaces() -> None:
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    with pytest.raises(RuntimeError, match="validation namespaces"):
        evaluate_paired(cfg, "missing.pt", split="ad_amr_test", samples=8)
    with pytest.raises(RuntimeError, match="validation namespaces"):
        evaluate_paired(cfg, "missing.pt", split="ad_amr_final_blind_test", samples=8)


def test_paired_evaluator_strictly_loads_real_v2_and_shares_records(tmp_path: Path) -> None:
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    cfg["device"] = "cpu"
    model = build_ad_amr_model(8, **cfg["model"])
    checkpoint = tmp_path / "candidate.pt"
    torch.save({"model_state": model.state_dict(), "loss_variant": "P0", "epoch": 0}, checkpoint)
    first = evaluate_paired(cfg, checkpoint, split="ad_amr_validation", samples=168)
    second = evaluate_paired(cfg, checkpoint, split="ad_amr_validation", samples=168)
    assert first["samples"] == 168
    assert first["sample_ids_sha256"] == second["sample_ids_sha256"]
    assert set(first["candidate"]["per_class_accuracy"]) == set(first["v2"]["per_class_accuracy"])
    assert first["final_blind_test_accessed"] is False


def test_profile_preserves_cpu_device() -> None:
    cfg = load_yaml("configs/ad_amr_v1.yaml")
    model = build_ad_amr_model(8, **cfg["model"])
    profile = profile_ad_amr_model(model, 1024)
    assert profile["parameters"] == 288236
    assert all(parameter.device.type == "cpu" for parameter in model.parameters())


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_production_cuda_train_evaluate_and_profile(tmp_path: Path) -> None:
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    cfg["device"] = "cuda:0"
    cfg["output_root"] = str(tmp_path / "cuda_production")
    cfg["training"]["amp"] = True
    cfg["dataset"]["train_samples"] = 64
    cfg["dataset"]["val_samples"] = 32
    result = run_training(cfg, stop_after_epoch=1)
    assert [row["epoch"] for row in result["history"]] == [1]
    checkpoint = Path(cfg["output_root"]) / "checkpoints/best.pt"
    report = evaluate(cfg, str(checkpoint), split="ad_amr_validation")
    assert report["final_blind_test_accessed"] is False
    assert torch.isfinite(torch.tensor(report["metrics"]["macro_f1"]))
