"""Strict-resume equivalence under V3.2's distillation + macro-F1 selection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
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
        rng = np.random.default_rng(np.random.SeedSequence([992, epoch, index]))
        values = torch.tensor(rng.normal(size=4), dtype=torch.float32)
        return values, int((index + epoch) % 2)


class TinyNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Dropout(0.2), nn.Linear(8, 2))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


def _training() -> dict:
    return {
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
        "distillation": {"enabled": True, "temperature": 4.0, "alpha": 0.7},
    }


def _teacher() -> nn.Module:
    torch.manual_seed(123)
    teacher = TinyNet().eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    return teacher


def _run(root: Path, *, stop: int | None = None, resume: Path | None = None) -> tuple[QAMAwareV32Trainer, list[dict]]:
    set_seed(77)
    config = {"seed": 77, "training": _training()}
    train_set = EpochDataset(32, "train")
    val_set = EpochDataset(16, "validation")
    generator = torch.Generator().manual_seed(77)
    train_loader = DataLoader(train_set, batch_size=8, shuffle=True, generator=generator)
    val_loader = DataLoader(val_set, batch_size=8, shuffle=False)
    trainer = QAMAwareV32Trainer(
        TinyNet(), torch.device("cpu"), config, ensure_output_dirs(root), ["zero", "one"], teacher=_teacher()
    )
    history = trainer.fit(train_loader, val_loader, resume_path=resume, stop_after_epoch=stop)
    return trainer, history


def _nested_equal(left, right) -> bool:
    if torch.is_tensor(left):
        return bool(torch.equal(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_nested_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_nested_equal(a, b) for a, b in zip(left, right))
    return left == right


def test_distillation_strict_resume_matches_continuous(tmp_path: Path) -> None:
    continuous, continuous_history = _run(tmp_path / "continuous")
    _, first_history = _run(tmp_path / "split", stop=2)
    resumed, resumed_history = _run(tmp_path / "split", resume=tmp_path / "split" / "checkpoints" / "last.pt")

    assert [row["epoch"] for row in first_history] == [1, 2]
    assert [row["epoch"] for row in resumed_history] == [1, 2, 3, 4]
    assert [row["epoch"] for row in continuous_history] == [1, 2, 3, 4]

    for left, right in zip(continuous_history, resumed_history):
        for key in left:
            if key == "training_time_sec":
                continue
            assert left[key] == right[key], f"history field {key!r} diverged"

    assert _nested_equal(continuous.model.state_dict(), resumed.model.state_dict())
    assert _nested_equal(continuous.optimizer.state_dict(), resumed.optimizer.state_dict())
    assert _nested_equal(continuous.scheduler.state_dict(), resumed.scheduler.state_dict())

    continuous_ckpt = torch.load(tmp_path / "continuous" / "checkpoints" / "last.pt", map_location="cpu", weights_only=False)
    resumed_ckpt = torch.load(tmp_path / "split" / "checkpoints" / "last.pt", map_location="cpu", weights_only=False)
    assert continuous_ckpt["best_epoch"] == resumed_ckpt["best_epoch"]
    assert continuous_ckpt["next_epoch"] == resumed_ckpt["next_epoch"] == 5
    assert continuous_ckpt["distillation"]["enabled"] is True
    assert resumed_ckpt["distillation"]["temperature"] == 4.0
