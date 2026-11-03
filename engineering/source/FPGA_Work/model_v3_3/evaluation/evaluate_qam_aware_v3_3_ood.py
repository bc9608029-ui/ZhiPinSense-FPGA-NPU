"""Synthetic out-of-distribution (OOD) validation for QAM-Aware V3.3.

Each OOD domain is a *synthetic* channel/config perturbation that the model was
not trained on (impairments disabled or weaker during training, or SNR points
outside the training range).  This is development diagnostics only — it never
claims real SDR/board measurements and never touches the blind set.

The OOD surface participates in Stage-1 candidate selection through the
``worst_domain_macro_f1`` summary (the minimum macro-F1 across every domain), and
is always evaluated on the validation namespace with the *selection seed* — never
on the development test or the final blind namespace.

Domains:

* ``cfo_strong``          — CFO far outside the training range, prob 1.0;
* ``sfo``                 — sampling-frequency offset (disabled in training);
* ``phase_offset``        — full-range random phase offset (beyond training);
* ``phase_noise``         — phase noise (disabled in training);
* ``iq_imbalance``        — gain/phase imbalance (disabled in training);
* ``rayleigh``            — Rayleigh flat fading (disabled in training);
* ``rician``              — Rician fading (disabled in training);
* ``multipath``           — multipath taps/delay (disabled in training);
* ``amplitude_scaling_wide`` — amplitude scale far outside training range;
* ``clipping``            — sample clipping (disabled in training);
* ``multi_impairment``    — cross-parameter-family holdout (CFO + multipath +
  IQ imbalance + phase noise enabled together);
* ``snr_ood``             — SNR points outside the [-20, 20] training range;
* ``sample_start_offset`` — random circular frame-start shift.

Every single-effect domain keeps AWGN on and disables the other randomizations so
the target effect is isolated.  Sample counts are recorded per domain.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.qam_aware_rfnet_v3_3 import build_qam_aware_v3_3, load_v2_into_v3_3
from training.metrics import classification_metrics
from training.qam_aware_v3_3_utils import load_qam_aware_v3_3_config
from training.utils import ensure_output_dirs, load_config, select_device, set_seed
from training.v3_3_split_guard import record_split

OOD_SNR = [-24.0, -22.0, 22.0, 24.0]


def _clean_channel(base: dict) -> dict:
    """AWGN on, every other effect off — the isolated OOD starting point."""

    channel = copy.deepcopy(base)
    for name in channel:
        if not isinstance(channel[name], dict):
            continue
        if "enabled" in channel[name]:
            channel[name]["enabled"] = name == "awgn"
            channel[name]["probability"] = 1.0 if name == "awgn" else 0.0
    return channel


def _domain_channels(base: dict) -> dict[str, dict]:
    """Return the synthetic OOD channel configs (excluding snr/sample-start)."""

    domains: dict[str, dict] = {}
    cfo = _clean_channel(base)
    cfo["cfo"].update({"enabled": True, "probability": 1.0, "hz": [-3000.0, 3000.0]})
    domains["cfo_strong"] = cfo

    sfo = _clean_channel(base)
    sfo["sfo"].update({"enabled": True, "probability": 1.0, "ppm": [-120.0, 120.0]})
    domains["sfo"] = sfo

    po = _clean_channel(base)
    po["phase_offset"].update({"enabled": True, "probability": 1.0, "radians": [-3.14159, 3.14159]})
    domains["phase_offset"] = po

    pn = _clean_channel(base)
    pn["phase_noise"].update({"enabled": True, "probability": 1.0, "std_rad": [0.002, 0.02]})
    domains["phase_noise"] = pn

    iqi = _clean_channel(base)
    iqi["iq_imbalance"].update({"enabled": True, "probability": 1.0, "gain_db": [-1.5, 1.5], "phase_deg": [-8.0, 8.0]})
    domains["iq_imbalance"] = iqi

    ray = _clean_channel(base)
    ray["rayleigh"].update({"enabled": True, "probability": 1.0})
    domains["rayleigh"] = ray

    ric = _clean_channel(base)
    ric["rician"].update({"enabled": True, "probability": 1.0, "k_factor": [2.0, 6.0]})
    domains["rician"] = ric

    mp = _clean_channel(base)
    mp["multipath"].update({"enabled": True, "probability": 1.0, "num_taps": [3, 8], "max_delay": 16})
    domains["multipath"] = mp

    amp = _clean_channel(base)
    amp["amplitude_scaling"].update({"enabled": True, "probability": 1.0, "scale": [0.4, 1.8]})
    domains["amplitude_scaling_wide"] = amp

    clip = _clean_channel(base)
    clip["clipping"].update({"enabled": True, "probability": 1.0, "level_rms": [1.2, 2.5]})
    domains["clipping"] = clip

    # Cross-parameter-family holdout: several independent families enabled
    # together, isolating nothing, to catch models that over-fit one family.
    multi = _clean_channel(base)
    multi["cfo"].update({"enabled": True, "probability": 1.0, "hz": [-1800.0, 1800.0]})
    multi["multipath"].update({"enabled": True, "probability": 1.0, "num_taps": [2, 6], "max_delay": 12})
    multi["iq_imbalance"].update({"enabled": True, "probability": 1.0, "gain_db": [-1.2, 1.2], "phase_deg": [-6.0, 6.0]})
    multi["phase_noise"].update({"enabled": True, "probability": 1.0, "std_rad": [0.001, 0.01]})
    domains["multi_impairment"] = multi

    return domains


@torch.inference_mode()
def _predict(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    targets: list[int] = []
    predictions: list[int] = []
    model.eval()
    for inputs, labels in loader:
        logits = model(inputs.to(device, non_blocking=True))
        targets.extend(labels.tolist())
        predictions.extend(logits.argmax(dim=1).cpu().tolist())
    return np.asarray(targets, dtype=np.int64), np.asarray(predictions, dtype=np.int64)


def _summarize(targets: np.ndarray, predictions: np.ndarray, classes: list[str]) -> dict:
    metrics = classification_metrics(targets, predictions, len(classes))
    per_class = np.asarray(metrics["per_class_accuracy"])
    qam = {name: per_class[classes.index(name)] for name in ("16QAM", "64QAM")}
    return {
        "samples": int(len(targets)),
        "accuracy": float(metrics["accuracy"]),
        "macro_f1": float(metrics["macro_f1"]),
        "qam_mean_accuracy": float(np.mean(list(qam.values()))),
        "per_class_accuracy": {name: float(per_class[classes.index(name)]) for name in classes},
    }


def _start_offset_collate(batch):
    iq, labels = zip(*batch)
    iq = torch.stack(iq)
    labels = torch.tensor(labels, dtype=torch.long)
    offsets = torch.randint(0, iq.shape[-1], (iq.shape[0],))
    for i in range(iq.shape[0]):
        iq[i] = torch.roll(iq[i], shifts=int(offsets[i]), dims=-1)
    return iq, labels


def _evaluate_ood_domains(
    *,
    model: torch.nn.Module,
    device: torch.device,
    config: dict,
    baseline: dict,
    classes: list[str],
    seed: int,
    samples: int,
) -> tuple[list[dict], float]:
    batch_size = int(config["evaluation"]["batch_size"])
    rows: list[dict] = []
    domains = _domain_channels(baseline["channel"])

    for name, channel in domains.items():
        record_split(f"ood_{name}")
        dataset = SyntheticModulationDataset(
            samples, config["signal"], channel, seed, f"ood_{name}",
            snr_values=baseline["dataset"]["snr_values"],
        )
        targets, predictions = _predict(
            model, DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0), device
        )
        rows.append({"domain": name, "type": "channel", **_summarize(targets, predictions, classes)})

    # SNR out-of-range domain (fixed points outside the training [-20, 20]).
    clean = _clean_channel(baseline["channel"])
    for snr in OOD_SNR:
        record_split(f"ood_snr_{snr}")
        dataset = SyntheticModulationDataset(
            samples, config["signal"], clean, seed, f"ood_snr_{snr}", fixed_snr_db=float(snr)
        )
        targets, predictions = _predict(
            model, DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0), device
        )
        rows.append({"domain": f"snr_{snr}", "type": "snr_ood", **_summarize(targets, predictions, classes)})

    # Sample-start offset (random circular frame shift).
    record_split("ood_start_offset")
    dataset = SyntheticModulationDataset(
        samples, config["signal"], clean, seed, "ood_start_offset",
        snr_values=baseline["dataset"]["snr_values"],
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0, collate_fn=_start_offset_collate)
    targets, predictions = _predict(model, loader, device)
    rows.append({"domain": "sample_start_offset", "type": "sample_start_offset", **_summarize(targets, predictions, classes)})

    worst_domain_macro_f1 = min(float(row["macro_f1"]) for row in rows)
    return rows, worst_domain_macro_f1


def _ood_defaults(config: dict, baseline: dict) -> tuple[int, int]:
    seed = int(baseline["seed"])
    samples = int(config["dataset"].get("val_samples", baseline["dataset"]["test_samples"]))
    return seed, samples


def evaluate_v3_3_ood(
    config_path: str,
    checkpoint_path: str | None = None,
    *,
    seed: int | None = None,
    samples: int | None = None,
) -> dict[str, object]:
    config = load_qam_aware_v3_3_config(config_path)
    baseline = load_config(config["_baseline_path"])
    default_seed, default_samples = _ood_defaults(config, baseline)
    eval_seed = default_seed if seed is None else int(seed)
    eval_samples = default_samples if samples is None else int(samples)
    set_seed(eval_seed)
    device = select_device(str(config.get("device", "auto")))
    paths = ensure_output_dirs(config["output_root"])
    checkpoint_file = Path(checkpoint_path) if checkpoint_path else paths["checkpoints"] / "best.pt"
    checkpoint = torch.load(checkpoint_file, map_location=device, weights_only=False)
    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    model = build_qam_aware_v3_3(len(classes), **config["model"]).to(device).eval()
    model.load_state_dict(checkpoint["model_state"])

    rows, worst_domain_macro_f1 = _evaluate_ood_domains(
        model=model, device=device, config=config, baseline=baseline, classes=classes,
        seed=eval_seed, samples=eval_samples,
    )

    report = {
        "checkpoint": str(checkpoint_file),
        "scope": "synthetic OOD only; no real SDR/board measurement claimed",
        "final_blind_test_accessed": False,
        "validation_seed": eval_seed,
        "samples_per_domain": eval_samples,
        "worst_domain_macro_f1": worst_domain_macro_f1,
        "domains": rows,
    }
    (paths["tables"] / "ood_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(paths["tables"] / "ood_validation.csv", index=False)
    return report


def evaluate_v3_3_a0_ood(
    config_path: str,
    v2_checkpoint_path: str | None = None,
    *,
    seed: int | None = None,
    samples: int | None = None,
) -> dict[str, object]:
    """OOD evaluation for the real frozen V2 champion (A0) on the validation namespace."""

    config = load_qam_aware_v3_3_config(config_path)
    baseline = load_config(config["_baseline_path"])
    default_seed, default_samples = _ood_defaults(config, baseline)
    eval_seed = default_seed if seed is None else int(seed)
    eval_samples = default_samples if samples is None else int(samples)
    set_seed(eval_seed)
    device = select_device(str(config.get("device", "auto")))
    v2_path = Path(v2_checkpoint_path) if v2_checkpoint_path else Path(config["v2_checkpoint"])
    v2_checkpoint = torch.load(v2_path, map_location=device, weights_only=False)
    classes = [str(name).upper() for name in config["signal"]["modulations"]]

    a0_model_config = dict(config["model"])
    a0_model_config["residual_expert"] = {"enabled": False}
    a0_model_config["family_aux"] = {"enabled": False}
    model = build_qam_aware_v3_3(len(classes), **a0_model_config).to(device).eval()
    load_v2_into_v3_3(model, v2_checkpoint)

    rows, worst_domain_macro_f1 = _evaluate_ood_domains(
        model=model, device=device, config=config, baseline=baseline, classes=classes,
        seed=eval_seed, samples=eval_samples,
    )

    return {
        "checkpoint": str(v2_path),
        "scope": "synthetic OOD only; no real SDR/board measurement claimed",
        "final_blind_test_accessed": False,
        "validation_seed": eval_seed,
        "samples_per_domain": eval_samples,
        "worst_domain_macro_f1": worst_domain_macro_f1,
        "domains": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_3_smoke.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--samples", type=int, default=None)
    args = parser.parse_args()
    print(json.dumps(evaluate_v3_3_ood(args.config, args.checkpoint, seed=args.seed, samples=args.samples), indent=2))


if __name__ == "__main__":
    main()
