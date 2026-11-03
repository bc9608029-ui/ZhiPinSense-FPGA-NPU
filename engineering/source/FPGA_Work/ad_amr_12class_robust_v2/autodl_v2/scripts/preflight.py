#!/usr/bin/env python3
"""V2 offline preflight / CPU smoke test.

Exercises the full V2 pipeline without a GPU: frozen contract, model build and
forward, V1-compatible dataset generation, augmentation groups, SNR curriculum,
V2 losses, the trainer loss, V1-compatible evaluation, result utilities, and
Phase-C candidate builders.  Prints PASS/FAIL per check and exits non-zero on
any failure.

Usage (from the package root):
    python3 scripts/preflight.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import torch

from training.utils import load_yaml
from v2.contract import V2_MODEL_NAME, assert_12class_contract
from v2.curriculum import active_snr_values
from v2.augmentation import GROUP_NAMES, V2Augmentor
from v2 import losses as v2_losses

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS  {name}")
    else:
        FAILURES.append(name)
        print(f"FAIL  {name}  {detail}")


def main() -> int:
    from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model, profile_ad_amr_v1_1

    config = load_yaml("configs/v2_base.yaml")
    signal = config["signal"]
    classes = [str(v).upper() for v in signal["modulations"]]

    # 1. frozen contract
    assert_12class_contract(signal)
    check("contract_12class", classes == list(
        "OOK 4ASK AM-DSB WBFM 2FSK GFSK BPSK QPSK 8PSK 16QAM 64QAM OFDM".split()))
    check("contract_sample_length", int(signal["sample_length"]) == 1024)

    # 2. model build + forward
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    profile = profile_ad_amr_v1_1(model, 1024)
    check("model_params", profile["parameters"] == 279036, str(profile["parameters"]))
    iq = torch.randn(1, 2, 1024)
    with torch.inference_mode():
        logits, denoised = model(iq)
    check("model_forward", tuple(logits.shape) == (1, 12) and tuple(denoised.shape) == (1, 2, 1024),
          f"logits={tuple(logits.shape)} denoised={tuple(denoised.shape)}")
    check("model_forward_finite", bool(torch.isfinite(logits).all()))

    # 3. dataset generation (baseline == V1 path)
    from v2.dataset_v2 import V2Dataset
    ds = V2Dataset(24, signal, config["channel"], 2026, "train",
                   snr_values=[float(v) for v in config["dataset"]["snr_values"]])
    item = ds[0]
    check("dataset_shapes", tuple(item["noisy_iq"].shape) == (2, 1024)
          and tuple(item["clean_iq"].shape) == (2, 1024), str(item["noisy_iq"].shape))
    check("dataset_label_range", 0 <= item["label"] < 12)
    check("dataset_snr", -20.0 <= item["snr_db"] <= 20.0)

    # 4. augmentation groups
    rng = np.random.default_rng(0)
    sample = np.random.randn(1024).astype(np.float32) + 1j * np.random.randn(1024).astype(np.float32)
    for name in GROUP_NAMES:
        aug = V2Augmentor([name])
        out = aug(sample, rng)
        check(f"augment_{name}_shape", out.shape == sample.shape)
        check(f"augment_{name}_finite", bool(np.isfinite(out).all()))
    aug_all = V2Augmentor(["A", "B", "C", "D"])
    check("augment_all", aug_all(sample, rng).shape == sample.shape)

    # 5. curriculum
    full = [float(v) for v in config["dataset"]["snr_values"]]
    check("curriculum_none", active_snr_values("none", full, 1, 100) == full)
    check("curriculum_low", all(v <= -2.0 for v in active_snr_values("very_low_first", full, 1, 100)))
    check("curriculum_warmup_full", active_snr_values("linear_warmup", full, 100, 100) == full)

    # 6. losses
    torch.manual_seed(0)
    logits = torch.randn(8, 12)
    labels = torch.randint(0, 12, (8,))
    for name in ("cross_entropy", "focal", "label_smoothing", "class_balanced"):
        fn = getattr(v2_losses, name)
        value = fn(logits, labels)
        check(f"loss_{name}", bool(torch.isfinite(value)) and value.ndim == 0, str(value))

    # 7. trainer loss path
    from v2.trainer import V2Trainer
    snr_db = torch.full((8,), 0.0)
    trainer = V2Trainer(config, {"checkpoints": Path(tempfile.mkdtemp()) / "ckpt",
                                 "logs": Path(tempfile.mkdtemp()) / "logs"}, classes)
    denoised = torch.randn(8, 2, 1024)
    clean = torch.randn(8, 2, 1024)
    cls_loss = trainer._classification_loss(logits, labels, snr_db)
    rec = torch.nn.functional.mse_loss(denoised, clean)
    total = cls_loss + trainer.reconstruction_weight * rec
    check("trainer_classification_loss", bool(torch.isfinite(cls_loss)) and cls_loss.ndim == 0)
    check("trainer_total_loss", bool(torch.isfinite(total)))

    # 8. V1-compatible evaluation with a synthetic checkpoint
    from v2.evaluate import evaluate_v1_1
    ckpt_dir = Path(tempfile.mkdtemp())
    ckpt_path = ckpt_dir / "best.pt"
    torch.save({"class_names": classes, "model_state": model.state_dict(), "epoch": 1}, ckpt_path)
    report = evaluate_v1_1(config, ckpt_path, samples=4)
    check("evaluate_v1_1", set(report["metrics"]) >= {"accuracy", "macro_f1", "rated_0_20_accuracy"},
          str(sorted(report["metrics"])))

    # 9. results utilities
    from v2.results import collect_trial_results, multi_seed_summary, prune, rank, write_summary_table
    fake = [{"trial": f"t{i}", "seed": 2026, "phase": "pilot", "history": [{"loss": 1.0}],
             "baseline": {"metrics": {"rated_0_20_accuracy": 0.9 - i * 0.05,
                                      "accuracy": 0.8, "macro_f1": 0.8, "snr_0_accuracy": 0.8,
                                      "min_per_class_accuracy": 0.7}}}
            for i in range(3)]
    kept, rejected = prune(fake)
    check("results_prune", len(kept) == 3 and len(rejected) == 0)
    check("results_rank", rank(fake)[0]["trial"] == "t0")
    check("results_multi_seed", multi_seed_summary(fake)["num_seeds"] == 3)

    # 10. Phase-C candidates
    from v2.architectures import CANDIDATE_INFO, build_candidate
    for name in CANDIDATE_INFO:
        cand = build_candidate(name, 12, **config["model"])
        with torch.inference_mode():
            cand_logits, _ = cand(iq)
        check(f"candidate_{name}", tuple(cand_logits.shape) == (1, 12))

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print(f"\nALL PASS ({V2_MODEL_NAME})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
