"""Release-blocking full-SNR numerical-stability gate for V3.3 (CUDA only).

This is the test that failed the real RTX 5090 Stage-1: formal data includes
-20 dB samples whose physical power plane reaches ~10^3, and the order-2/order-4
moment products overflow FP16 (Inf/NaN) when the residual expert is fed the raw
physical features.  Phase 5 adds a deployable input clamp (Add/Mul/Relu over
pre-registered buffers) before ``HigherOrderMomentPool``; this gate proves, on a
real GPU, for every residual variant (A1/A2/A3) and the full 21-SNR suite, that:

   1. autocast FP16 is actually enabled;
   2. the -20 dB physical planes exceed the [-2, 2] deploy contract and are
      clamped back to it (|expert input| <= 2) with finite order-4 moments;
   3. forward / each loss component / total loss / backward / gradients /
      optimizer step are all finite under FP16 autocast;
   4. gate=0 initialization still reproduces V2 element-wise;
   5. the final residual stays bounded by ``residual_bound``;
   6. the ONNX partition still passes checker/opset-17/8-op-whitelist.

Skipped on a CPU-only host; ``ready`` must never rely on this skip (the CUDA
preflight re-runs it on the GPU).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import torch
import torch.nn.functional as functional
from torch import nn
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.qam_aware_rfnet_v3_3 import (
    build_qam_aware_v3_3,
    build_qam_aware_v3_3_partition,
    load_v2_into_v3_3,
    v3_3_family_ids,
)
from scripts.export_qam_aware_v3_3_onnx import OPSET_VERSION, _gate_partition, _inspect
from training.qam_aware_v3_3_trainer import QAMAwareV33Trainer
from training.qam_aware_v3_3_utils import load_qam_aware_v3_3_config
from training.train_qam_aware_v3_3 import _build_v2_teacher, verify_init_matches_v2
from training.utils import ensure_output_dirs, set_seed

FULL_SNR = [-20, -18, -16, -14, -12, -10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
REAL_V2_MODEL_STATE_KEYS = 91


def _config_for(variant: str, tmp_path: Path) -> dict:
    config = load_qam_aware_v3_3_config("configs/qam_aware_v3_3.yaml")
    config["output_root"] = str(tmp_path / "outputs")
    config["device"] = "cuda:0"
    config["dataset"]["train_samples"] = 256
    config["dataset"]["val_samples"] = 96
    config["dataset"]["test_samples"] = 64
    config["dataset"]["snr_values"] = FULL_SNR
    config["training"]["epochs"] = 1
    config["training"]["batch_size"] = 32
    config["training"]["minimum_epochs_before_stopping"] = 1
    config["training"]["amp"] = True
    config["model"]["residual_expert"]["enabled"] = True
    config["model"]["residual_expert"]["residual_bound"] = 1.0
    config["model"]["residual_expert"]["input_clamp_bound"] = 2.0
    if variant in ("A2", "A3"):
        config["model"]["family_aux"]["enabled"] = True
        config["training"]["family_aux_loss_weight"] = 1.0
    if variant == "A3":
        config["training"]["domain_consistency"]["enabled"] = True
        config["training"]["domain_consistency"]["weight"] = 1.0
    return config


def _loader(dataset: SyntheticModulationDataset, config: dict, device: torch.device, *, train: bool) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=int(config["training"]["batch_size"]),
        shuffle=train,
        generator=torch.Generator().manual_seed(int(config["seed"])) if train else None,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )


def _batch(dataset: SyntheticModulationDataset, indices: list[int], device: torch.device):
    inputs = torch.stack([dataset[i][0] for i in indices]).to(device)
    labels = torch.tensor([dataset[i][1] for i in indices], device=device)
    return inputs, labels


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
@pytest.mark.parametrize("variant", ["A1", "A2", "A3"])
def test_full_snr_numeric_stability(tmp_path: Path, variant: str) -> None:
    device = torch.device("cuda:0")
    assert torch.cuda.is_available()

    config = _config_for(variant, tmp_path)
    seed = int(config["seed"])
    set_seed(seed)

    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    num_classes = len(classes)
    sample_length = int(config["signal"]["sample_length"])
    assert (num_classes, sample_length) == (8, 1024)

    v2_path = Path(config["v2_checkpoint"])
    v2_ckpt = torch.load(v2_path, map_location="cpu", weights_only=False)
    assert len(v2_ckpt["model_state"]) == REAL_V2_MODEL_STATE_KEYS

    student = build_qam_aware_v3_3(num_classes, **config["model"])
    load_v2_into_v3_3(student, v2_ckpt)
    teacher = _build_v2_teacher(v2_ckpt, num_classes)
    student = student.to(device)
    teacher = teacher.to(device)

    # (4) gate=0 initialization reproduces V2 element-wise, on CUDA.
    init_diff = verify_init_matches_v2(student, teacher, sample_length)
    assert init_diff < 1e-6

    # (1)+(3) a real QAMAwareV33Trainer runs one epoch over the full 21-SNR suite
    # under FP16 autocast; the modified FP32-loss path must stay finite end-to-end.
    paths = ensure_output_dirs(config["output_root"])
    train_set = SyntheticModulationDataset(
        int(config["dataset"]["train_samples"]), config["signal"], config["channel"],
        seed, "v3_3_train", snr_values=[float(v) for v in config["dataset"]["snr_values"]],
    )
    val_set = SyntheticModulationDataset(
        int(config["dataset"]["val_samples"]), config["signal"], config["channel"],
        seed, "v3_3_validation", snr_values=[float(v) for v in config["dataset"]["snr_values"]],
    )
    train_loader = _loader(train_set, config, device, train=True)
    val_loader = _loader(val_set, config, device, train=False)

    trainer = QAMAwareV33Trainer(student, device, config, paths, classes)
    assert trainer.amp_enabled is True, "autocast FP16 must be enabled on CUDA"
    assert trainer.scaler.is_enabled() is True
    history = trainer.fit(train_loader, val_loader, stop_after_epoch=1)
    assert [row["epoch"] for row in history] == [1]
    assert all(
        torch.isfinite(torch.tensor(row["train_loss"])) and torch.isfinite(torch.tensor(row["val_loss"]))
        for row in history
    )

    # (2) -20 dB physical planes exceed the deploy contract and are clamped to it.
    minus20 = SyntheticModulationDataset(
        32, config["signal"], config["channel"], seed, "v3_3_train", fixed_snr_db=-20.0
    )
    iq20, _ = _batch(minus20, list(range(32)), device)
    with torch.no_grad():
        _, physical = student.prepare_inputs(iq20)
        assert physical.abs().max().item() > 2.0, "expected -20 dB physical power > 2"

        clamped = student.core.expert.prepare_physical(physical)
        assert clamped.abs().max().item() <= 2.0 + 1e-4
        moments = student.core.expert.moments(physical)
        assert torch.isfinite(moments).all()

        # The actual FP16 regression: the full forward (including the moment pool)
        # must stay finite under autocast with -20 dB input.
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=True):
            assert torch.is_autocast_enabled("cuda") is True
            logits20 = student(iq20)
            assert torch.isfinite(logits20).all()

    # (3) explicit per-component finiteness + backward + gradients + step.
    student.train()
    inputs, labels = next(iter(train_loader))
    inputs, labels = inputs.to(device), labels.to(device)
    trainable = [p for p in student.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=1e-3)
    criterion = nn.CrossEntropyLoss()
    family_map = v3_3_family_ids(num_classes).to(device)

    family_loss = None
    residual_loss = None
    domain_loss = None
    with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=True):
        assert torch.is_autocast_enabled("cuda") is True
        logits, aux = student.forward_with_aux(inputs)
        assert torch.isfinite(logits).all()
        ce_loss = criterion(logits, labels)
        assert torch.isfinite(ce_loss).all()
        loss = ce_loss
        if "family" in aux:
            family_loss = criterion(aux["family"], family_map[labels])
            assert torch.isfinite(family_loss).all()
            loss = loss + family_loss
        if "residual" in aux:
            residual_loss = (aux["residual"].float() ** 2).mean()
            assert torch.isfinite(residual_loss).all()
            loss = loss + config["training"]["residual_penalty_weight"] * residual_loss
        if config["training"]["domain_consistency"]["enabled"]:
            hw_logits = student.forward_domain(inputs, hardware_sim=True)
            domain_loss = functional.mse_loss(logits.float(), hw_logits.detach().float())
            assert torch.isfinite(domain_loss).all()
            loss = loss + config["training"]["domain_consistency"]["weight"] * domain_loss
        assert torch.isfinite(loss).all()

    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    for parameter in trainable:
        assert parameter.grad is None or torch.isfinite(parameter.grad).all(), "non-finite gradient"
    optimizer.step()
    for parameter in trainable:
        assert torch.isfinite(parameter).all(), "non-finite parameter after step"

    # (6) ONNX partition still passes checker / opset-17 / 8-op whitelist.
    # The export graph must be an independent deep copy: build_qam_aware_v3_3_partition
    # returns student.core (parameters *shared*, not copied), so calling .cpu() on it
    # directly would move the live CUDA student's backbone off-device and break the
    # residual-bound test below.  deepcopy first, then move only the copy to CPU.
    source_partition = build_qam_aware_v3_3_partition(student)
    partition = copy.deepcopy(source_partition).eval().cpu()
    iq0 = torch.zeros(1, 2, sample_length, dtype=torch.float32)
    phys0 = torch.zeros(1, 3, sample_length, dtype=torch.float32)
    onnx_path = tmp_path / f"partition_{variant}.onnx"
    torch.onnx.export(
        partition,
        (iq0, phys0),
        str(onnx_path),
        opset_version=OPSET_VERSION,
        input_names=["iq", "physical_features"],
        output_names=["logits"],
        dynamo=False,
    )
    inspection = _inspect(onnx_path)
    _gate_partition(inspection)
    assert inspection["opset"] == OPSET_VERSION

    # (6b) exporting the deep copy must not have moved the live student off-device.
    for parameter in student.parameters():
        assert parameter.device == device, (
            f"live student parameter drifted to {parameter.device} (expected {device})"
        )
    for buffer in student.buffers():
        assert buffer.device == device, (
            f"live student buffer drifted to {buffer.device} (expected {device})"
        )

    # (5) final residual stays bounded by residual_bound under extreme weights/gate.
    with torch.no_grad():
        for parameter in student.core.expert.parameters():
            parameter.mul_(50.0)
        student.core.expert.gate.copy_(torch.tensor([100.0], device=device))
    student.eval()
    with torch.no_grad():
        _, aux = student.forward_with_aux(iq20)
        residual = aux["residual"]
        assert residual.abs().max().item() <= 1.0 + 1e-5
