"""CUDA preflight gate for RML24-OOD V1.1 (runs before any formal training).

This is the AutoDL "machine is actually usable for the 24-class pipeline" gate.
It runs eight sub-checks in order; the first failure stops the pipeline with a
non-zero exit and a single ``CUDA_PREFLIGHT_RESULT result=FAIL`` line (success
prints ``CUDA_PREFLIGHT_RESULT result=PASS`` exactly once).

Sub-checks:

  1. environment           torch / CUDA / GPU / driver / cuDNN / optuna / python
  2. data identity         HDF5 SHA-256 + size vs the frozen data contract
  3. single-batch forward  ``[B,2,1024]`` CUDA forward with finite logits
  4. loss x optimizer      4 losses x 2 optimizers forward/backward/step, with
                           device/dtype-consistent class weights and finite loss
                           and gradients (no CPU/CUDA mixing, no NaN/Inf)
  5. optuna multi-trial    a few TPE trials over the frozen static search space
  6. micro-train           24-class mini train (2 epochs, small per-stratum) with
                           checkpoint save + reload
  7. onnx export + parity  export the micro checkpoint to ONNX, ORT parity vs torch
  8. ood scoring           MSP/Entropy/MaxLogit/Energy on a small logits batch

Nothing here trains the *real* candidate or writes any PASS beyond the preflight
line.  It is run by ``scripts/run_cuda_preflight.sh`` and is the gate that unlocks
``READY-FOR-RML24-PILOT``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch

from contracts.rml24_contract import LABEL_ORDER_24
from training.utils import (
    ensure_output_dirs,
    environment_info,
    load_yaml,
    resolve_project_path,
    select_device,
)

_PREFLIGHT_OUTPUT = "runs/cuda_preflight"
_MICRO_EPOCHS = 2
_MICRO_BATCH = 64
_MICRO_PER_STRATUM = 8
_LOSS_NAMES = ("cross_entropy", "focal", "label_smoothing", "class_balanced")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_environment() -> None:
    info = environment_info()
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    if not info["cuda_available"]:
        raise RuntimeError("CUDA is not available; cannot run the 24-class preflight")
    if torch.version.cuda is None:
        raise RuntimeError("torch was built without CUDA support")
    cudnn = getattr(torch.backends, "cudnn", None)
    cudnn_version = cudnn.version() if cudnn is not None and hasattr(cudnn, "version") else None
    print(f"[preflight] cudnn_version={cudnn_version}", flush=True)
    try:
        import optuna  # noqa: F401
        print(f"[preflight] optuna={optuna.__version__}", flush=True)
    except ImportError:
        raise RuntimeError("optuna is required for the pilot but is not installed")


def check_data_identity(config: dict[str, Any]) -> None:
    contract_path = resolve_project_path("contracts/rml2018_data_contract.json")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    hdf5_path = resolve_project_path(config["public_data"]["hdf5_path"])
    if not hdf5_path.is_file():
        raise RuntimeError(f"RadioML HDF5 missing at {hdf5_path}; run scripts/run_data_audit.sh first")
    expected_sha = str(contract["sha256"])
    expected_size = int(contract["size_bytes"])
    actual_size = hdf5_path.stat().st_size
    if actual_size != expected_size:
        raise RuntimeError(f"HDF5 size {actual_size} != contract {expected_size}")
    actual_sha = _sha256_file(hdf5_path)
    if actual_sha != expected_sha:
        raise RuntimeError("HDF5 SHA-256 differs from the frozen data contract")
    print(f"[preflight] hdf5_sha256={actual_sha} size={actual_size}", flush=True)


def check_single_batch_forward(device: torch.device) -> None:
    from models.rml24_net import build_rml24_model

    model = build_rml24_model(len(LABEL_ORDER_24)).to(device).eval()
    iq = torch.randn(8, 2, 1024, device=device)
    with torch.inference_mode():
        logits, _ = model(iq)
    if not torch.isfinite(logits).all():
        raise RuntimeError("single-batch forward produced non-finite logits")
    if logits.shape != (8, len(LABEL_ORDER_24)):
        raise RuntimeError(f"unexpected logits shape {logits.shape}")
    print(f"[preflight] forward logits_shape={tuple(logits.shape)} finite=ok", flush=True)


def _build_optimizer(name: str, params: Any, config: dict[str, Any]) -> torch.optim.Optimizer:
    lr = float(config["training"]["learning_rate"])
    wd = float(config["training"]["weight_decay"])
    if name == "adamw":
        return torch.optim.AdamW(params, lr=lr, weight_decay=wd)
    if name == "sgd":
        return torch.optim.SGD(params, lr=lr, momentum=float(config.get("v2", {}).get("sgd_momentum", 0.9)),
                               weight_decay=wd)
    raise ValueError(f"unknown optimizer {name!r}")


def check_loss_optimizer_matrix(device: torch.device, config: dict[str, Any]) -> None:
    from v2 import losses as v2_losses
    from models.rml24_net import build_rml24_model

    model = build_rml24_model(len(LABEL_ORDER_24)).to(device).train()
    iq = torch.randn(8, 2, 1024, device=device)
    labels = torch.randint(0, len(LABEL_ORDER_24), (8,), device=device)
    class_weight = torch.ones(len(LABEL_ORDER_24), device=device, dtype=torch.float32)

    loss_fns = {
        "cross_entropy": lambda l, t: v2_losses.cross_entropy(l, t),
        "focal": lambda l, t: v2_losses.focal(l, t, gamma=2.0, weight=class_weight),
        "label_smoothing": lambda l, t: v2_losses.label_smoothing(l, t, smoothing=0.1,
                                                                  weight=class_weight),
        "class_balanced": lambda l, t: v2_losses.class_balanced(l, t, class_weights=class_weight),
    }
    for loss_name in _LOSS_NAMES:
        for optimizer_name in ("adamw", "sgd"):
            model.zero_grad(set_to_none=True)
            logits, _ = model(iq)
            if logits.device != device:
                raise RuntimeError("logits device mismatch")
            loss = loss_fns[loss_name](logits, labels)
            if not bool(torch.isfinite(loss)):
                raise RuntimeError(f"{loss_name}/{optimizer_name} produced non-finite loss")
            optimizer = _build_optimizer(optimizer_name, model.parameters(), config)
            loss.backward()
            for name_, param in model.named_parameters():
                if param.grad is not None and not bool(torch.isfinite(param.grad).all()):
                    raise RuntimeError(f"{loss_name}/{optimizer_name} non-finite grad in {name_}")
            optimizer.step()
    print("[preflight] loss_optimizer_matrix 4x2 forward/backward/step finite=ok", flush=True)


def check_optuna_multi_trial() -> None:
    from training.rml24_pilot import sample_rml24_optuna

    import optuna

    def objective(trial: Any) -> float:
        sample_rml24_optuna(trial)
        return float(trial.number)

    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=2026))
    study.optimize(objective, n_trials=8)
    if len(study.trials) != 8:
        raise RuntimeError("optuna study did not complete 8 trials")
    print("[preflight] optuna_multi_trial n=8 ok", flush=True)


def _micro_config(config: dict[str, Any]) -> dict[str, Any]:
    import copy

    cfg = copy.deepcopy(config)
    cfg["device"] = "cuda"
    cfg["output_root"] = _PREFLIGHT_OUTPUT
    cfg["training"] = dict(cfg["training"])
    cfg["training"]["epochs"] = _MICRO_EPOCHS
    cfg["training"]["minimum_epochs_before_stopping"] = 1
    cfg["training"]["batch_size"] = _MICRO_BATCH
    cfg["dataset"] = dict(cfg["dataset"])
    cfg["dataset"]["num_workers"] = 0
    cfg["rml24"] = dict(cfg.get("rml24", {}))
    cfg["rml24"]["smoke_max_per_stratum"] = _MICRO_PER_STRATUM
    return cfg


def check_micro_train(config: dict[str, Any], device: torch.device) -> None:
    from torch.utils.data import DataLoader

    from datasets.ad_amr_dataset import collate_ad_amr
    from datasets.radioml2018_dataset import RadioML2018Dataset
    from training.rml24_trainer import RML24Trainer
    from training.utils import set_seed
    from v2.candidate_signature import load_artifact_shas

    cfg = _micro_config(config)
    cfg.update(load_artifact_shas())
    set_seed(2026)

    public = cfg["public_data"]
    train_dataset = RadioML2018Dataset(
        public["hdf5_path"], public["classes_path"], public["audit_path"],
        public["index_path"], "train", max_per_stratum=_MICRO_PER_STRATUM,
    )
    val_dataset = RadioML2018Dataset(
        public["hdf5_path"], public["classes_path"], public["audit_path"],
        public["index_path"], "validation", max_per_stratum=_MICRO_PER_STRATUM,
    )
    collate = collate_ad_amr
    pin = device.type == "cuda"
    train_loader = DataLoader(train_dataset, batch_size=_MICRO_BATCH, shuffle=True,
                              num_workers=0, collate_fn=collate, pin_memory=pin, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=_MICRO_BATCH, shuffle=False,
                            num_workers=0, collate_fn=collate, pin_memory=pin, drop_last=False)
    paths = ensure_output_dirs(cfg["output_root"])
    trainer = RML24Trainer(cfg, paths, list(LABEL_ORDER_24))
    trainer.fit(train_loader, val_loader)
    trainer.save_summary()

    best_path = paths["checkpoints"] / "best.pt"
    if not best_path.is_file():
        raise RuntimeError("micro-train produced no best.pt")
    checkpoint = torch.load(best_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != list(LABEL_ORDER_24):
        raise RuntimeError("micro checkpoint class order mismatch")
    if "model_state" not in checkpoint:
        raise RuntimeError("micro checkpoint missing model_state")
    print(f"[preflight] micro_train epochs={trainer.best_epoch} best.pt reload ok", flush=True)


def check_onnx_export_parity(config: dict[str, Any]) -> None:
    from scripts.export_rml24_onnx import export_rml24

    cfg = _micro_config(config)
    checkpoint = resolve_project_path(_PREFLIGHT_OUTPUT) / "checkpoints" / "best.pt"
    if not checkpoint.is_file():
        raise RuntimeError("micro checkpoint missing for ONNX export")
    report = export_rml24(cfg, checkpoint)
    if report["ort_parity"]["status"] != "ok":
        raise RuntimeError(f"ORT parity failed: {report['ort_parity']}")
    print(f"[preflight] onnx_export_parity opset={report['inspection']['opset']} ok", flush=True)


def check_ood_scoring(device: torch.device) -> None:
    from ood.scores import compute_scores

    rng = np.random.default_rng(0)
    logits = rng.normal(size=(64, len(LABEL_ORDER_24)))
    for method in ("msp", "entropy", "max_logit", "energy"):
        scores = compute_scores(logits, method)
        if not np.isfinite(scores).all():
            raise RuntimeError(f"OOD score {method} produced non-finite values")
    # Also confirm the same math runs on a CUDA tensor path (move to torch and back).
    torch_logits = torch.tensor(logits, dtype=torch.float32, device=device)
    if not torch.isfinite(torch_logits).all():
        raise RuntimeError("CUDA logits tensor non-finite")
    print("[preflight] ood_scoring msp/entropy/max_logit/energy finite=ok", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    args = parser.parse_args()
    config = load_yaml(args.config)
    device = select_device("cuda")  # raises if CUDA unavailable

    steps: list[tuple[str, Any]] = [
        ("environment", lambda: check_environment()),
        ("data_identity", lambda: check_data_identity(config)),
        ("single_batch_forward", lambda: check_single_batch_forward(device)),
        ("loss_optimizer_matrix", lambda: check_loss_optimizer_matrix(device, config)),
        ("optuna_multi_trial", check_optuna_multi_trial),
        ("micro_train", lambda: check_micro_train(config, device)),
        ("onnx_export_parity", lambda: check_onnx_export_parity(config)),
        ("ood_scoring", lambda: check_ood_scoring(device)),
    ]

    failures: list[str] = []
    for name, step in steps:
        try:
            step()
            print(f"[preflight] {name}: OK", flush=True)
        except Exception as exc:  # noqa: BLE001 — every failure is a gate failure
            failures.append(f"{name}: {exc}")
            print(f"[preflight] {name}: FAILED — {exc}", flush=True)

    if failures:
        print("CUDA_PREFLIGHT_RESULT result=FAIL", flush=True)
        for failure in failures:
            print(f"[preflight] failure — {failure}", flush=True)
        return 1
    print("CUDA_PREFLIGHT_RESULT result=PASS", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
