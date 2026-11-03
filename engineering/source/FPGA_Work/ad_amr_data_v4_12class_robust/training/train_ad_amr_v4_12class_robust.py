"""Data-v4 robustness fine-tune: twelve-class best -> augmented train channel.

PROVISIONAL — experiment scaffold.

Fine-tunes the FROZEN twelve-class model from its own best checkpoint (not from
public pretraining) at low learning rate, applying the config-driven augmented
channel (``robust.train_channel``) **only** to the train split.  Validation and
OOD stay on the frozen baseline ``ChannelPipeline`` via the unchanged evaluator.

Nothing here changes the model structure: the network is the same twelve-class
``ADAMRV11Net``, and only the classifier output width was ever 10 -> 12 (already
frozen upstream).  ONNX export, the operator whitelist, and the formal gates are
all reused unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset, collate_ad_amr
from datasets.ad_amr_v4_robust_dataset import ADAMRV4RobustDataset
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from models.ad_amr_v1_1_teachers import TeacherEnsemble
from training.ad_amr_v1_1_trainer import ADAMRV11Trainer
from training.train_ad_amr_v1_1 import _sha256
from training.train_ad_amr_v1_1_data_v3_12class import assert_twelve_class_contract
from training.utils import ensure_output_dirs, load_yaml, resolve_project_path, save_json, select_device, set_seed


def _dict_sha256(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def build_robust_dataloaders(config: dict[str, Any], device: torch.device):
    """Train loader uses the augmented channel; validation stays frozen."""
    dataset_cfg = config["dataset"]
    snr_values = [float(v) for v in dataset_cfg["snr_values"]]
    seed = int(config["seed"])
    train_set = ADAMRV4RobustDataset(
        int(dataset_cfg["train_samples"]), config["signal"], config["channel"], seed,
        "ad_amr_v1_4_robust_train", snr_values=snr_values,
        train_channel_config=config["robust"]["train_channel"],
    )
    val_set = ADAMRV11Dataset(
        int(dataset_cfg["val_samples"]), config["signal"], config["channel"], seed,
        "ad_amr_v1_1_validation", snr_values=snr_values,
    )
    common = {
        "batch_size": int(config["training"]["batch_size"]),
        "num_workers": int(dataset_cfg.get("num_workers", 0)),
        "collate_fn": collate_ad_amr,
        "pin_memory": device.type == "cuda",
    }
    train = DataLoader(train_set, shuffle=True, generator=torch.Generator().manual_seed(seed), **common)
    val = DataLoader(val_set, shuffle=False, **common)
    return train, val


def _init_from_checkpoint(model: Any, checkpoint_path: str | Path,
                          classes: list[str]) -> dict[str, Any]:
    """Load the twelve-class best checkpoint weights into ``model`` (strict)."""
    source = resolve_project_path(checkpoint_path)
    if not source.is_file():
        raise FileNotFoundError(
            f"robust init checkpoint is missing: {source}; the twelve-class formal "
            "best.pt must exist before a robustness fine-tune"
        )
    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != classes:
        raise RuntimeError("init checkpoint class contract differs from the twelve-class contract")
    model.load_state_dict(checkpoint["model_state"], strict=True)
    return {
        "checkpoint": str(source),
        "checkpoint_sha256": _sha256(source),
        "source_epoch": int(checkpoint.get("epoch", -1)),
        "mode": "fine_tune_from_twelve_class_best",
    }


def run_robust_training(
    config_or_path: dict[str, Any] | str,
    *,
    resume: bool = False,
    stop_after_epoch: int | None = None,
) -> dict[str, Any]:
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    assert_twelve_class_contract(config)
    robust = config.get("robust")
    if not robust or "train_channel" not in robust:
        raise RuntimeError("robustness fine-tune requires a `robust.train_channel` section")
    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(config.get("device", "auto"))
    classes = [str(value).upper() for value in config["signal"]["modulations"]]
    paths = ensure_output_dirs(config["output_root"])
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    train_loader, val_loader = build_robust_dataloaders(config, device)
    teachers = TeacherEnsemble(config, device)
    last = paths["checkpoints"] / "last.pt"
    init_provenance: dict[str, Any] | None = None

    if resume and last.exists():
        model = model.to(device)
        trainer = ADAMRV11Trainer(model, teachers, device, config, paths, classes)
        trainer.load_resume(last, train_loader)
    else:
        init_path = str(robust["init_checkpoint"]).format(seed=seed)
        init_provenance = _init_from_checkpoint(model, init_path, classes)
        model = model.to(device)
        trainer = ADAMRV11Trainer(model, teachers, device, config, paths, classes)

    history = trainer.fit(train_loader, val_loader, stop_after_epoch)
    if not history or trainer.best_epoch <= 0:
        raise RuntimeError("robust fine-tune produced no best checkpoint")
    best = next(row for row in history if int(row["epoch"]) == trainer.best_epoch)
    result = {
        "seed": seed,
        "candidate": robust.get("candidate"),
        "init": init_provenance or {"mode": "strict_resume"},
        "train_channel_sha256": _dict_sha256(robust["train_channel"]),
        "train_split": "ad_amr_v1_4_robust_train",
        "val_split": "ad_amr_v1_1_validation",
        "architecture_changed_from_v1_1": False,
        "architecture_change_scope": "none (twelve-class head and trunk unchanged)",
        "best_epoch": trainer.best_epoch,
        "best_selection_score": trainer.best_score,
        "best_validation_macro_f1": best["val_macro_f1"],
        "best_validation_accuracy": best["val_accuracy"],
        "best_validation_rated_0_20_accuracy": best["val_rated_0_20_accuracy"],
        "best_validation_snr_0_accuracy": best["val_snr_0_accuracy"],
        "history": history,
        "selection_scope": "target synthetic train/validation only; public test and final blind not accessed",
    }
    save_json(result, paths["checkpoints"] / "training_summary.json")
    return result


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1_data_v4_12class_robust.yaml")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-epoch", type=int, default=None)
    args = parser.parse_args()
    result = run_robust_training(args.config, resume=args.resume, stop_after_epoch=args.stop_after_epoch)
    print(
        f"best_epoch={result['best_epoch']} best_f1={result['best_validation_macro_f1']:.6f} "
        f"rated={result['best_validation_rated_0_20_accuracy']:.6f}", flush=True,
    )


if __name__ == "__main__":
    main()
