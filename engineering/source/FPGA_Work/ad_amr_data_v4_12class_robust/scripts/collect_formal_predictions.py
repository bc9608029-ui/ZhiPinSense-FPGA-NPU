"""Collect per-record predictions from the robustness formal checkpoints (eval-only).

Reads the two formal ``best.pt`` checkpoints (seed2026/seed2027) and emits, for each
of the eight domains — validation, fake-int8, and the six OOD channels — a JSONL of
per-record predictions plus a 12x12 confusion matrix, per-class accuracy, and a
global manifest.  It never accesses the public test or the final blind split and
performs no training.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset, collate_ad_amr
from evaluation.evaluate_ad_amr_v1_1 import ood_channels
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from training.utils import PROJECT_ROOT, load_yaml, resolve_project_path, select_device

FORMAL_CONFIG = "configs/ad_amr_v1_1_data_v4_12class_robust_formal.yaml"
OUT_ROOT = PROJECT_ROOT / "outputs/ad_amr_v1_1_data_v4_12class_robust/formal/predictions"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_model(config: dict[str, Any], checkpoint_path: Path, device: torch.device,
                classes: list[str], fake_int8: bool) -> tuple[torch.nn.Module, str]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != classes:
        raise RuntimeError("checkpoint and evaluation class orders differ")
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    if fake_int8:
        with torch.no_grad():
            for parameter in model.parameters():
                maximum = float(parameter.abs().max())
                if maximum > 0.0:
                    scale = maximum / 127.0
                    parameter.copy_(torch.clamp(torch.round(parameter / scale), -127, 127) * scale)
    return model.to(device).eval(), _sha256(checkpoint_path)


def _collect(config: dict[str, Any], checkpoint_path: Path, split: str,
             channel: dict[str, Any] | None, fake_int8: bool, domain: str) -> dict[str, Any]:
    device = select_device(config.get("device", "auto"))
    classes = [str(v).upper() for v in config["signal"]["modulations"]]
    model, checkpoint_sha256 = _load_model(config, checkpoint_path, device, classes, fake_int8)
    count = int(config["evaluation"]["samples"] if domain in {"validation", "fake_int8"}
                else config["evaluation"]["ood_samples"])
    dataset = ADAMRV11Dataset(
        count, config["signal"], channel or config["channel"], int(config["seed"]), split,
        snr_values=[float(v) for v in config["dataset"]["snr_values"]],
    )
    loader = DataLoader(dataset, batch_size=int(config["evaluation"]["batch_size"]),
                        shuffle=False, num_workers=0, collate_fn=collate_ad_amr,
                        pin_memory=device.type == "cuda")
    records: list[dict[str, Any]] = []
    with torch.inference_mode():
        for batch in loader:
            logits, _ = model(batch["noisy_iq"].to(device, non_blocking=True))
            if not bool(torch.isfinite(logits).all()):
                raise RuntimeError(f"non-finite logits in {split}")
            predictions = logits.argmax(1).cpu().tolist()
            labels = batch["label"].tolist()
            snrs = batch["snr_db"].tolist()
            sample_ids = batch["sample_id"].tolist()
            for index, (sid, label, pred, snr) in enumerate(
                zip(sample_ids, labels, predictions, snrs)
            ):
                records.append({
                    "seed": int(config["seed"]), "domain": domain,
                    "record_index": int(index), "sample_id": int(sid),
                    "label": int(label), "pred": int(pred), "snr_db": float(snr),
                    "checkpoint_sha256": checkpoint_sha256,
                })
    confusion = [[0] * len(classes) for _ in range(len(classes))]
    for record in records:
        confusion[record["label"]][record["pred"]] += 1
    per_class_accuracy: dict[str, float] = {}
    for class_index, name in enumerate(classes):
        hits = sum(1 for r in records if r["label"] == class_index and r["pred"] == class_index)
        total = sum(1 for r in records if r["label"] == class_index)
        per_class_accuracy[name] = float(hits / total) if total else 0.0
    correct = sum(1 for r in records if r["label"] == r["pred"])
    return {
        "records": records, "confusion": confusion, "per_class_accuracy": per_class_accuracy,
        "accuracy": float(correct / len(records)) if records else 0.0,
        "checkpoint_sha256": checkpoint_sha256, "classes": classes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=FORMAL_CONFIG)
    parser.add_argument("--checkpoints", default=str(PROJECT_ROOT / "outputs/ad_amr_v1_1_data_v4_12class_robust/formal"))
    parser.add_argument("--out", default=str(OUT_ROOT))
    args = parser.parse_args()

    base = load_yaml(args.config)
    seeds = [int(v) for v in base["robust"]["formal"]["seeds"]]
    checkpoints_root = resolve_project_path(args.checkpoints)
    out_root = resolve_project_path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    channels = ood_channels(base["channel"])
    domains = ["validation", "fake_int8"] + list(channels)

    manifest: dict[str, Any] = {
        "class_contract": base["signal"]["modulations"],
        "seeds": seeds,
        "domains": domains,
        "config": args.config,
        "domains_detail": {},
    }
    for seed in seeds:
        checkpoint = checkpoints_root / f"seed{seed}" / "checkpoints" / "best.pt"
        if not checkpoint.is_file():
            raise SystemExit(f"formal checkpoint is missing: {checkpoint}")
        for domain in domains:
            if domain == "validation":
                split, channel, fake_int8 = "ad_amr_v1_1_validation", None, False
            elif domain == "fake_int8":
                split, channel, fake_int8 = "ad_amr_v1_1_data_v3_12class_validation_fake_int8", None, True
            else:
                split = f"ad_amr_v1_1_data_v3_12class_validation_ood_{domain}"
                channel, fake_int8 = channels[domain], False
            result = _collect(base, checkpoint, split, channel, fake_int8, domain)
            domain_dir = out_root / f"seed{seed}" / domain
            domain_dir.mkdir(parents=True, exist_ok=True)
            with (domain_dir / "records.jsonl").open("w", encoding="utf-8") as handle:
                for record in result["records"]:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            with (domain_dir / "confusion.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["label\\pred"] + result["classes"])
                for class_index, name in enumerate(result["classes"]):
                    writer.writerow([name] + result["confusion"][class_index])
            with (domain_dir / "per_class_accuracy.json").open("w", encoding="utf-8") as handle:
                json.dump({
                    "per_class_accuracy": result["per_class_accuracy"],
                    "accuracy": result["accuracy"],
                    "checkpoint_sha256": result["checkpoint_sha256"],
                    "num_records": len(result["records"]),
                }, handle, ensure_ascii=False, indent=2)
            manifest["domains_detail"][f"seed{seed}/{domain}"] = {
                "num_records": len(result["records"]),
                "accuracy": result["accuracy"],
                "checkpoint_sha256": result["checkpoint_sha256"],
            }
    with (out_root / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    print(f"wrote predictions for seeds={seeds} domains={domains} to {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
