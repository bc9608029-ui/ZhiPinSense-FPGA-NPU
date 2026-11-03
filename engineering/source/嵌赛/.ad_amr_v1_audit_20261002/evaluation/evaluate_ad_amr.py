"""AD-AMR V1 evaluation: full metric suite + split-access guard.

Evaluates a trained checkpoint over a requested split and emits accuracy,
macro-F1, Cohen's kappa, per-class accuracy, confusion matrix, per-SNR accuracy,
the 0-10 dB slice, the QAM mean, and the denoising MSE (to both the noisy and
clean targets).  It also writes ``access_audit.json`` recording exactly which
split namespaces were touched, and asserts the final blind test is never read.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_dataset import ADAMRPairDataset, collate_ad_amr
from models.ad_amr_net import build_ad_amr_model, profile_ad_amr_model
from training.metrics import classification_metrics, qam_mean
from training.utils import ensure_output_dirs, load_yaml, save_json, select_device

FORBIDDEN_SPLITS = ("final_blind_test", "ad_amr_final_blind_test")


def evaluate(config: dict[str, Any], checkpoint_path: str | None = None,
             split: str = "ad_amr_test") -> dict[str, Any]:
    device = select_device(config.get("device", "auto"))
    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    num_classes = len(classes)
    sample_length = int(config["signal"]["sample_length"])
    paths = ensure_output_dirs(config["output_root"])

    # Split guard: never allow the final blind test namespace here.
    if split in FORBIDDEN_SPLITS:
        raise RuntimeError(f"refusing to evaluate forbidden split {split!r}")

    checkpoint_file = Path(checkpoint_path) if checkpoint_path else paths["checkpoints"] / "best.pt"
    checkpoint = torch.load(checkpoint_file, map_location="cpu", weights_only=False)
    loss_variant = checkpoint.get("loss_variant", config["training"]["loss"]["variant"])

    model = build_ad_amr_model(num_classes, **config["model"]).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    dataset_cfg = config["dataset"]
    snr_values = [float(v) for v in dataset_cfg["snr_values"]]
    samples = int(dataset_cfg.get("test_samples", 8400)) if split == "ad_amr_test" else int(dataset_cfg.get("val_samples", 5040))
    dataset = ADAMRPairDataset(
        samples, config["signal"], config["channel"], int(config["seed"]), split, snr_values=snr_values
    )
    loader = DataLoader(
        dataset, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False,
        num_workers=0, collate_fn=collate_ad_amr,
    )

    all_logits: list[torch.Tensor] = []
    all_targets: list[int] = []
    all_snr: list[float] = []
    denoise_to_clean: list[float] = []
    denoise_to_noisy: list[float] = []
    sample_ids: list[int] = []

    start = time.perf_counter()
    with torch.inference_mode():
        for batch in loader:
            clean = batch["clean_iq"].to(device)
            noisy = batch["noisy_iq"].to(device)
            logits, denoised = model(noisy)
            all_logits.append(logits.cpu())
            all_targets.extend(batch["label"].tolist())
            all_snr.extend(batch["snr_db"].tolist())
            sample_ids.extend(batch["sample_id"].tolist())
            denoise_to_clean.append(((denoised.cpu() - clean.cpu()) ** 2).mean(dim=(1, 2)))
            denoise_to_noisy.append(((denoised.cpu() - noisy.cpu()) ** 2).mean(dim=(1, 2)))
    eval_time = time.perf_counter() - start

    logits = torch.cat(all_logits)
    predictions = logits.argmax(dim=1).tolist()
    metrics = classification_metrics(all_targets, predictions, num_classes)
    metrics["qam_mean"] = qam_mean(metrics["per_class_accuracy"], classes)

    # Per-SNR accuracy.
    snr_buckets: dict[str, list[bool]] = {}
    for pred, target, snr in zip(predictions, all_targets, all_snr):
        key = f"{snr:.0f}"
        snr_buckets.setdefault(key, []).append(pred == target)
    per_snr = {key: float(sum(v) / len(v)) for key, v in sorted(snr_buckets.items(), key=lambda kv: float(kv[0]))}

    # 0-10 dB slice.
    in_slice = [pred == target for pred, target, snr in zip(predictions, all_targets, all_snr) if 0.0 <= snr <= 10.0]
    metrics["accuracy_0_10db"] = float(sum(in_slice) / len(in_slice)) if in_slice else float("nan")

    denoise_clean = torch.cat(denoise_to_clean)
    denoise_noisy = torch.cat(denoise_to_noisy)
    metrics["denoising_mse_to_clean"] = float(denoise_clean.mean().item())
    metrics["denoising_mse_to_noisy"] = float(denoise_noisy.mean().item())

    profile = profile_ad_amr_model(model, sample_length)

    report = {
        "checkpoint": str(checkpoint_file),
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "loss_variant": loss_variant,
        "split": split,
        "num_samples": len(all_targets),
        "class_order": classes,
        "eval_time_sec": eval_time,
        "metrics": metrics,
        "per_snr_accuracy": per_snr,
        "profile": profile,
        "final_blind_test_accessed": False,
        "sample_ids_min": int(min(sample_ids)) if sample_ids else None,
        "sample_ids_max": int(max(sample_ids)) if sample_ids else None,
    }

    output = paths["checkpoints"].parent
    save_json(report, output / f"evaluation_{split}.json")

    access_audit = {
        "accessed_splits": [split],
        "forbidden_splits_accessed": [],
        "final_blind_test_accessed": False,
        "note": "final blind test namespace is never read by training or evaluation",
    }
    save_json(access_audit, output / "access_audit.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--split", default="ad_amr_test")
    args = parser.parse_args()
    config = load_yaml(args.config)
    report = evaluate(config, args.checkpoint, args.split)
    m = report["metrics"]
    print(json.dumps({
        "split": report["split"],
        "accuracy": m["accuracy"],
        "macro_f1": m["macro_f1"],
        "cohen_kappa": m["cohen_kappa"],
        "qam_mean": m["qam_mean"],
        "accuracy_0_10db": m["accuracy_0_10db"],
        "denoising_mse_to_clean": m["denoising_mse_to_clean"],
        "denoising_mse_to_noisy": m["denoising_mse_to_noisy"],
        "params": report["profile"]["parameters"],
    }, indent=2))


if __name__ == "__main__":
    main()
