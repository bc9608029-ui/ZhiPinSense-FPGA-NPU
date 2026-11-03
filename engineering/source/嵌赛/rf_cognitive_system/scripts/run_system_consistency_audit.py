"""Generate a non-blind, read-only trace and numerical consistency report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from channel.channel_pipeline import ChannelPipeline
from datasets.modulation_generator import generate_iq
from datasets.synthetic_dataset import SyntheticModulationDataset
from deployment.numerical_contract import (
    NumericalContract,
    consistency_metrics,
    planned_fpga_tensors_from_int16,
    reference_tensors_from_int16,
)
from deployment.time_power_phase_partition import external_physical_features, load_formal_candidate
from training.qam_aware_utils import load_qam_aware_config
from training.utils import resolve_project_path


def _stats(iq: np.ndarray) -> dict[str, float]:
    power = np.abs(iq) ** 2
    return {
        "mean_power": float(np.mean(power)),
        "rms": float(np.sqrt(np.mean(power))),
        "peak_magnitude": float(np.max(np.abs(iq))),
    }


def run_audit(config_path: str, output_path: str) -> dict[str, object]:
    config = load_qam_aware_config(config_path)
    dataset = SyntheticModulationDataset(
        5040,
        config["signal"],
        config["channel"],
        seed=int(config["seed"]),
        split="validation",
        return_metadata=True,
        snr_values=config["dataset"]["snr_values"],
    )
    tensor, label, metadata = dataset[0]
    rng = np.random.default_rng(np.random.SeedSequence(metadata["seed_key"]))
    clean, signal_metadata = generate_iq(config["signal"]["modulations"][label], config["signal"], rng)
    channel_output, channel_metadata = ChannelPipeline(config["channel"], config["signal"]["sample_rate"])(
        clean, rng, snr_db=float(metadata["assigned_snr_db"])
    )
    reconstructed = np.stack((channel_output.real, channel_output.imag)).astype(np.float32)

    model, checkpoint = load_formal_candidate(config_path)
    with torch.inference_mode():
        batched = tensor.unsqueeze(0)
        physical = external_physical_features(model, batched)
        logits = model(batched)

    int_rng = np.random.default_rng(20260909)
    iq_int16 = np.clip(np.rint(int_rng.normal(0.0, 6000.0, size=(1024, 2))), -32768, 32767).astype(np.int16)
    numerical_contract = NumericalContract()
    reference = reference_tensors_from_int16(iq_int16, numerical_contract)
    planned = planned_fpga_tensors_from_int16(iq_int16, numerical_contract)
    numerical_metrics = consistency_metrics(reference, planned, numerical_contract)

    report: dict[str, object] = {
        "scope": "Validation sample index 0 and deterministic SDR-like vectors only; final_blind_test not constructed or accessed.",
        "sample_trace": {
            "split": "validation",
            "index": 0,
            "class_index": int(label),
            "modulation": config["signal"]["modulations"][label],
            "seed_key": metadata["seed_key"],
            "assigned_snr_db": metadata["assigned_snr_db"],
            "clean": _stats(clean),
            "channel_output": _stats(channel_output),
            "dataset_reconstruction_max_abs_error": float(np.max(np.abs(tensor.numpy() - reconstructed))),
            "effects": channel_metadata["effects"],
            "signal_metadata": signal_metadata,
            "channel_metadata": channel_metadata,
            "tensor": {"shape": list(tensor.shape), "dtype": str(tensor.dtype)},
            "physical": {
                "shape": list(physical.shape),
                "dtype": str(physical.dtype),
                "channel_order": ["power", "lag1_real", "lag1_imag"],
            },
            "network": {
                "checkpoint_epoch": int(checkpoint["epoch"]),
                "output_shape": list(logits.shape),
                "finite": bool(torch.isfinite(logits).all()),
                "prediction_values_intentionally_omitted": True,
            },
        },
        "normalization": {
            "clean_generator_formula": "x *= amplitude / sqrt(mean(abs(x)**2))",
            "clean_amplitude": float(config["signal"]["amplitude"]),
            "epsilon": float(np.finfo(np.float64).eps),
            "post_channel_per_record_normalization": False,
            "network_input_batchnorm": False,
            "physical_branch_input_batchnorm": {
                "affine": False,
                "eps": 1e-5,
                "momentum": 0.1,
                "evaluation_uses_running_statistics": True,
            },
        },
        "fixed_point_consistency": {
            "contract": numerical_contract.__dict__,
            "metrics": numerical_metrics,
        },
    }
    destination = resolve_project_path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2.yaml")
    parser.add_argument("--output", default="outputs/system_consistency_audit/audit_report.json")
    args = parser.parse_args()
    print(json.dumps(run_audit(args.config, args.output), indent=2))


if __name__ == "__main__":
    main()
