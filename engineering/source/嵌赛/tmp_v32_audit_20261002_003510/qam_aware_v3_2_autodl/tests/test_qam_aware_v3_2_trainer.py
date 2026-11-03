"""Direct checks of V3.2 distillation and checkpoint-selection behaviour."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn.functional as functional
from torch import nn
from torch.utils.data import DataLoader, Dataset

from training.qam_aware_v3_2_trainer import QAMAwareV32Trainer
from training.utils import ensure_output_dirs, set_seed


class EpochDataset(Dataset):
    def __init__(self, size: int, split: str) -> None:
        self.size = size
        self.split = split
        self.epoch = 0

    def set_epoch(self, epoch: int) -> None:
        if self.split == "train":
            self.epoch = int(epoch)

    def __len__(self) -> int:
        return self.size

    def __getitem__(self, index: int):
        epoch = self.epoch if self.split == "train" else 0
        rng = np.random.default_rng(np.random.SeedSequence([202, epoch, index]))
        values = torch.tensor(rng.normal(size=4), dtype=torch.float32)
        return values, int((index + epoch) % 2)


class TinyNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Dropout(0.2), nn.Linear(8, 2))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


def _training(**overrides: object) -> dict:
    training = {
        "epochs": 4,
        "batch_size": 8,
        "optimizer": "AdamW",
        "learning_rate": 0.002,
        "weight_decay": 0.0001,
        "scheduler": "cosine",
        "early_stopping_patience": 20,
        "min_delta": 0.0,
        "checkpoint_metric": "val_macro_f1",
        "checkpoint_mode": "max",
        "class_weights": None,
        "label_smoothing": 0.0,
        "gradient_clip_norm": 0.0,
        "amp": False,
        "distillation": {"enabled": False},
    }
    training.update(overrides)
    return training


def _make_trainer(tmp_path: Path, teacher: nn.Module | None = None, **training_overrides: object) -> QAMAwareV32Trainer:
    config = {"seed": 55, "training": _training(**training_overrides)}
    model = TinyNet()
    return QAMAwareV32Trainer(
        model,
        torch.device("cpu"),
        config,
        ensure_output_dirs(tmp_path),
        ["zero", "one"],
        teacher=teacher,
    )


def test_distillation_loss_equals_alpha_t2_kl() -> None:
    torch.manual_seed(0)
    teacher = nn.Linear(8, 8)
    trainer = QAMAwareV32Trainer(
        TinyNet(),
        torch.device("cpu"),
        {"seed": 1, "training": _training(distillation={"enabled": True, "temperature": 4.0, "alpha": 0.7})},
        ensure_output_dirs(Path("outputs/qam_aware_v3_2/_unit_tmp")),
        ["a", "b", "c", "d", "e", "f", "g", "h"],
        teacher=teacher,
    )
    student_logits = torch.randn(6, 8)
    teacher_logits = torch.randn(6, 8)
    actual = trainer._distillation_loss(student_logits, teacher_logits)

    temperature = 4.0
    alpha = 0.7
    student_log_prob = functional.log_softmax(student_logits / temperature, dim=1)
    teacher_prob = functional.softmax(teacher_logits / temperature, dim=1)
    expected = alpha * (temperature**2) * functional.kl_div(
        student_log_prob, teacher_prob, reduction="batchmean"
    )
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


def test_distillation_requires_teacher_when_enabled(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no teacher"):
        _make_trainer(tmp_path, teacher=None, distillation={"enabled": True, "temperature": 4.0, "alpha": 0.7})


def test_teacher_is_frozen_and_in_eval_mode(tmp_path: Path) -> None:
    teacher = TinyNet().train()
    trainer = _make_trainer(tmp_path, teacher=teacher, distillation={"enabled": True, "temperature": 4.0, "alpha": 0.7})
    assert trainer.teacher.training is False
    assert all(parameter.requires_grad is False for parameter in trainer.teacher.parameters())
    teacher_ids = {id(parameter) for parameter in trainer.teacher.parameters()}
    optimizer_ids = {id(parameter) for group in trainer.optimizer.param_groups for parameter in group["params"]}
    assert teacher_ids.isdisjoint(optimizer_ids)


def test_distillation_fit_produces_finite_loss_and_best_checkpoint(tmp_path: Path) -> None:
    set_seed(55)
    teacher = TinyNet().eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    config = {"seed": 55, "training": _training(distillation={"enabled": True, "temperature": 4.0, "alpha": 0.7})}
    model = TinyNet()
    trainer = QAMAwareV32Trainer(
        model, torch.device("cpu"), config, ensure_output_dirs(tmp_path), ["zero", "one"], teacher=teacher
    )
    train_set = EpochDataset(32, "train")
    val_set = EpochDataset(16, "validation")
    generator = torch.Generator().manual_seed(55)
    train_loader = DataLoader(train_set, batch_size=8, shuffle=True, generator=generator)
    val_loader = DataLoader(val_set, batch_size=8, shuffle=False)
    history = trainer.fit(train_loader, val_loader)
    assert history
    assert all(np.isfinite(row["train_loss"]) and np.isfinite(row["val_loss"]) for row in history)
    best = torch.load(tmp_path / "checkpoints" / "best.pt", map_location="cpu", weights_only=False)
    assert best["distillation"]["enabled"] is True
    assert best["distillation"]["temperature"] == 4.0


def test_checkpoint_selection_tracks_macro_f1_maximum(tmp_path: Path) -> None:
    set_seed(55)
    config = {"seed": 55, "training": _training()}
    model = TinyNet()
    trainer = QAMAwareV32Trainer(model, torch.device("cpu"), config, ensure_output_dirs(tmp_path), ["zero", "one"])
    train_set = EpochDataset(32, "train")
    val_set = EpochDataset(16, "validation")
    generator = torch.Generator().manual_seed(55)
    history = trainer.fit(
        DataLoader(train_set, batch_size=8, shuffle=True, generator=generator),
        DataLoader(val_set, batch_size=8, shuffle=False),
    )
    best = torch.load(tmp_path / "checkpoints" / "best.pt", map_location="cpu", weights_only=False)
    f1_by_epoch = {row["epoch"]: row["val_macro_f1"] for row in history}
    expected_epoch = max(f1_by_epoch, key=f1_by_epoch.get)
    assert best["best_epoch"] == expected_epoch
    assert best["checkpoint_metric"] == "val_macro_f1"
    assert best["checkpoint_mode"] == "max"
