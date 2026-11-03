"""Supervised RadioML 2018.01A pretraining for the unchanged V1.1 network."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_dataset import collate_ad_amr
from datasets.radioml2018_dataset import RadioML2018Dataset, load_audit, read_class_names
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model, profile_ad_amr_v1_1
from training.ad_amr_v1_1_trainer import ADAMRV11Trainer
from training.utils import ensure_output_dirs, load_yaml, save_json, select_device, set_seed


def build_public_dataloaders(config: dict[str, Any], device: torch.device):
    public = config["public_data"]
    cfg = config["public_pretraining"]
    common = {
        "hdf5_path": public["hdf5_path"],
        "classes_path": public["classes_path"],
        "audit_path": public["audit_path"],
        "index_path": public["index_path"],
        "allowed_snrs": public.get("allowed_snrs"),
    }
    train_set = RadioML2018Dataset(
        **common, split="train", max_per_stratum=cfg.get("max_train_per_stratum")
    )
    val_set = RadioML2018Dataset(
        **common, split="validation", max_per_stratum=cfg.get("max_validation_per_stratum")
    )
    loader_common = {
        "batch_size": int(cfg["batch_size"]),
        "num_workers": int(cfg.get("num_workers", 0)),
        "collate_fn": collate_ad_amr,
        "pin_memory": device.type == "cuda",
    }
    generator = torch.Generator().manual_seed(int(config["seed"]))
    train_loader = DataLoader(train_set, shuffle=True, generator=generator, **loader_common)
    val_loader = DataLoader(val_set, shuffle=False, **loader_common)
    return train_loader, val_loader


def public_training_config(config: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    result["training"] = copy.deepcopy(config["public_pretraining"])
    result["output_root"] = str(config["public_pretraining"]["output_root"])
    result["signal"]["modulations"] = list(read_class_names(config["public_data"]["classes_path"]))
    if float(result["training"].get("reconstruction_weight", -1.0)) != 0.0:
        raise RuntimeError("public pretraining must keep reconstruction_weight=0")
    if bool(result["training"].get("distillation", {}).get("enabled", True)):
        raise RuntimeError("public pretraining must keep distillation disabled")
    return result


def run_public_pretraining(config_or_path: dict[str, Any] | str, *, resume: bool = False,
                           stop_after_epoch: int | None = None) -> dict[str, Any]:
    source = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    config = public_training_config(source)
    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(config.get("device", "auto"))
    classes = [str(value) for value in config["signal"]["modulations"]]
    audit = load_audit(config["public_data"]["audit_path"])
    config["_checkpoint_metadata"] = {
        "dataset": "RadioML2018.01A",
        "dataset_sha256": audit["sha256"],
        "index_sha256": audit["index_sha256"],
        "public_test_accessed": False,
    }
    paths = ensure_output_dirs(config["output_root"])
    model = build_ad_amr_v1_1_model(len(classes), **config["model"]).to(device)
    train_loader, val_loader = build_public_dataloaders(config, device)
    trainer = ADAMRV11Trainer(model, None, device, config, paths, classes)
    last = paths["checkpoints"] / "last.pt"
    if resume and last.exists():
        trainer.load_resume(last, train_loader)
    history = trainer.fit(train_loader, val_loader, stop_after_epoch)
    if not history or trainer.best_epoch <= 0:
        raise RuntimeError("public pretraining produced no best checkpoint")
    best = next(row for row in history if int(row["epoch"]) == trainer.best_epoch)
    result = {
        "dataset": "RadioML2018.01A",
        "dataset_sha256": audit["sha256"],
        "index_sha256": audit["index_sha256"],
        "public_test_accessed": False,
        "class_names": classes,
        "seed": seed,
        "best_epoch": trainer.best_epoch,
        "best_selection_score": trainer.best_score,
        "best_validation_macro_f1": best["val_macro_f1"],
        "best_validation_accuracy": best["val_accuracy"],
        "profile": profile_ad_amr_v1_1(model, int(config["signal"]["sample_length"])),
        "history": history,
    }
    save_json(result, paths["checkpoints"] / "training_summary.json")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1_data_v2.yaml")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-epoch", type=int, default=None)
    args = parser.parse_args()
    result = run_public_pretraining(args.config, resume=args.resume,
                                    stop_after_epoch=args.stop_after_epoch)
    print(
        f"best_epoch={result['best_epoch']} "
        f"best_validation_macro_f1={result['best_validation_macro_f1']:.6f}", flush=True,
    )


if __name__ == "__main__":
    main()
