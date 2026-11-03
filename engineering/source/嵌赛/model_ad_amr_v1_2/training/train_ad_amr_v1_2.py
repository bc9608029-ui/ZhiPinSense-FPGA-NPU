"""AD-AMR V1.2 data-robustness training entrypoint."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_v1_2_dataset import ADAMRV12Dataset, collate_ad_amr_v1_2
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model, profile_ad_amr_v1_1
from models.ad_amr_v1_1_teachers import TeacherEnsemble
from training.ad_amr_v1_2_trainer import ADAMRV12Trainer, training_signature
from training.utils import ensure_output_dirs, load_yaml, resolve_project_path, save_json, select_device, set_seed


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with resolve_project_path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_v1_2_dataloaders(config: dict[str, Any], device: torch.device):
    dataset_cfg = config["dataset"]
    snr_values = [float(value) for value in dataset_cfg["snr_values"]]
    seed = int(config["seed"])
    train_set = ADAMRV12Dataset(
        int(dataset_cfg["train_samples"]), config["signal"], config["channel"],
        config.get("data_robustness", {}), seed, "ad_amr_v1_2_train", snr_values=snr_values,
    )
    # Validation intentionally stays on the unchanged V1.1 distribution.  The
    # held-out stronger profiles are evaluated separately by the pilot/formal gates.
    val_set = ADAMRV12Dataset(
        int(dataset_cfg["val_samples"]), config["signal"], config["channel"],
        {"enabled": False}, seed, "ad_amr_v1_2_validation", snr_values=snr_values,
    )
    common = {
        "batch_size": int(config["training"]["batch_size"]),
        "num_workers": int(dataset_cfg.get("num_workers", 0)),
        "collate_fn": collate_ad_amr_v1_2,
        "pin_memory": device.type == "cuda",
    }
    train = DataLoader(train_set, shuffle=True, generator=torch.Generator().manual_seed(seed), **common)
    validation = DataLoader(val_set, shuffle=False, **common)
    return train, validation


def run_v1_2_training(config: dict[str, Any], resume: bool = False,
                      stop_after_epoch: int | None = None) -> dict[str, Any]:
    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(config.get("device", "auto"))
    classes = [str(value).upper() for value in config["signal"]["modulations"]]
    paths = ensure_output_dirs(config["output_root"])
    model = build_ad_amr_v1_1_model(len(classes), **config["model"]).to(device)
    teachers = TeacherEnsemble(config, device)
    train_loader, val_loader = build_v1_2_dataloaders(config, device)
    trainer = ADAMRV12Trainer(model, teachers, device, config, paths, classes)
    last = paths["checkpoints"] / "last.pt"
    if resume and last.exists():
        trainer.load_resume(last, train_loader)
    history = trainer.fit(train_loader, val_loader, stop_after_epoch)
    best = next(row for row in history if int(row["epoch"]) == trainer.best_epoch)
    result = {
        "track": "ad_amr_v1_2",
        "seed": seed,
        "best_epoch": trainer.best_epoch,
        "best_selection_score": trainer.best_score,
        "best_validation_macro_f1": best["val_macro_f1"],
        "best_validation_accuracy": best["val_accuracy"],
        "best_validation_rated_0_20_accuracy": best["val_rated_0_20_accuracy"],
        "best_validation_snr_0_accuracy": best["val_snr_0_accuracy"],
        "training_signature": training_signature(config),
        "data_robustness": config.get("data_robustness", {}),
        "profile_probabilities_at_best_epoch": train_loader.dataset.profile_probabilities(trainer.best_epoch),
        "profile_probabilities_at_final_epoch": train_loader.dataset.profile_probabilities(len(history)),
        "profile": profile_ad_amr_v1_1(model, int(config["signal"]["sample_length"])),
        "teacher_sha256": {
            "v2": _sha256(config["teachers"]["v2"]),
            "v1": [_sha256(path) for path in config["teachers"]["v1"]],
        },
        "history": history,
        "selection_scope": "train/validation only; final blind was not instantiated",
    }
    save_json(result, paths["checkpoints"] / "training_summary.json")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_2.yaml")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-epoch", type=int, default=None)
    args = parser.parse_args()
    result = run_v1_2_training(load_yaml(args.config), args.resume, args.stop_after_epoch)
    print(
        f"best_epoch={result['best_epoch']} best_f1={result['best_validation_macro_f1']:.6f} "
        f"rated={result['best_validation_rated_0_20_accuracy']:.6f}", flush=True,
    )


if __name__ == "__main__":
    main()
