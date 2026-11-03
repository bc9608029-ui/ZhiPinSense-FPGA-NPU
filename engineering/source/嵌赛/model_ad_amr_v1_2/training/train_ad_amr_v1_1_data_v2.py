"""Fine-tune the unchanged ten-class V1.1 network from public pretraining."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

import torch

from models.ad_amr_v1_1_net import ADAMRV11Net, build_ad_amr_v1_1_model, profile_ad_amr_v1_1
from models.ad_amr_v1_1_teachers import TeacherEnsemble
from training.ad_amr_v1_1_trainer import ADAMRV11Trainer
from training.train_ad_amr_v1_1 import _sha256, build_v1_1_dataloaders
from training.utils import ensure_output_dirs, load_yaml, resolve_project_path, save_json, select_device, set_seed


CLASSIFIER_OUTPUT_KEYS = frozenset({"classifier.3.weight", "classifier.3.bias"})


def load_public_trunk(model: ADAMRV11Net, checkpoint_path: str | Path) -> dict[str, Any]:
    source = resolve_project_path(checkpoint_path)
    if not source.is_file():
        raise FileNotFoundError(
            f"public pretraining checkpoint is missing: {source}; synthetic-only fallback is forbidden"
        )
    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    provenance = checkpoint.get("checkpoint_metadata", {})
    if provenance.get("dataset") != "RadioML2018.01A":
        raise RuntimeError("public checkpoint is missing RadioML2018.01A provenance")
    if provenance.get("public_test_accessed") is not False:
        raise RuntimeError("public checkpoint provenance does not prove test isolation")
    if len(str(provenance.get("dataset_sha256", ""))) != 64:
        raise RuntimeError("public checkpoint is missing the audited dataset SHA-256")
    classes = list(checkpoint.get("class_names", []))
    if len(classes) != 24:
        raise RuntimeError(f"public checkpoint must have 24 classes, received {len(classes)}")
    source_state = checkpoint.get("model_state")
    if not isinstance(source_state, dict):
        raise RuntimeError("public checkpoint has no model_state")
    target_state = model.state_dict()
    copied: list[str] = []
    for name, target in target_state.items():
        if name in CLASSIFIER_OUTPUT_KEYS:
            continue
        source_tensor = source_state.get(name)
        if source_tensor is None or tuple(source_tensor.shape) != tuple(target.shape):
            raise RuntimeError(f"public checkpoint trunk mismatch at {name}")
        target_state[name] = source_tensor.detach().clone()
        copied.append(name)
    unexpected = sorted(set(source_state) - set(target_state))
    if unexpected:
        raise RuntimeError(f"unexpected public checkpoint tensors: {unexpected}")
    model.load_state_dict(target_state, strict=True)
    expected = set(target_state) - CLASSIFIER_OUTPUT_KEYS
    if set(copied) != expected:
        raise RuntimeError("public checkpoint transfer was incomplete")
    return {
        "checkpoint": str(source),
        "checkpoint_sha256": _sha256(source),
        "source_epoch": int(checkpoint.get("epoch", -1)),
        "copied_tensor_count": len(copied),
        "excluded_tensors": sorted(CLASSIFIER_OUTPUT_KEYS),
    }


def run_data_v2_training(config_or_path: dict[str, Any] | str, *, resume: bool = False,
                         stop_after_epoch: int | None = None,
                         initialize_from_public: bool = True) -> dict[str, Any]:
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(config.get("device", "auto"))
    classes = [str(value).upper() for value in config["signal"]["modulations"]]
    paths = ensure_output_dirs(config["output_root"])
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    train_loader, val_loader = build_v1_1_dataloaders(config, device)
    teachers = TeacherEnsemble(config, device)
    last = paths["checkpoints"] / "last.pt"
    transfer: dict[str, Any] | None = None

    if resume and last.exists():
        model = model.to(device)
        trainer = ADAMRV11Trainer(model, teachers, device, config, paths, classes)
        trainer.load_resume(last, train_loader)
    else:
        if initialize_from_public:
            transfer = load_public_trunk(model, config["initialization"]["public_checkpoint"])
        model = model.to(device)
        trainer = ADAMRV11Trainer(model, teachers, device, config, paths, classes)

    history = trainer.fit(train_loader, val_loader, stop_after_epoch)
    if not history or trainer.best_epoch <= 0:
        raise RuntimeError("V1.1 data-v2 training produced no best checkpoint")
    best = next(row for row in history if int(row["epoch"]) == trainer.best_epoch)
    result = {
        "seed": seed,
        "initialization": transfer or {"mode": "strict_resume" if resume else "scratch"},
        "architecture_changed_from_v1_1": False,
        "best_epoch": trainer.best_epoch,
        "best_selection_score": trainer.best_score,
        "best_validation_macro_f1": best["val_macro_f1"],
        "best_validation_accuracy": best["val_accuracy"],
        "best_validation_rated_0_20_accuracy": best["val_rated_0_20_accuracy"],
        "best_validation_snr_0_accuracy": best["val_snr_0_accuracy"],
        "profile": profile_ad_amr_v1_1(model, int(config["signal"]["sample_length"])),
        "teacher_sha256": {
            "v2": _sha256(config["teachers"]["v2"]),
            "v1": [_sha256(path) for path in config["teachers"]["v1"]],
        },
        "history": history,
        "selection_scope": "target synthetic train/validation only; public test and final blind not accessed",
    }
    save_json(result, paths["checkpoints"] / "training_summary.json")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1_data_v2.yaml")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--scratch", action="store_true")
    parser.add_argument("--stop-after-epoch", type=int, default=None)
    args = parser.parse_args()
    result = run_data_v2_training(
        args.config, resume=args.resume, stop_after_epoch=args.stop_after_epoch,
        initialize_from_public=not args.scratch,
    )
    print(
        f"best_epoch={result['best_epoch']} best_f1={result['best_validation_macro_f1']:.6f} "
        f"rated={result['best_validation_rated_0_20_accuracy']:.6f}", flush=True,
    )


if __name__ == "__main__":
    main()
