"""V3.3 trainer: residual/aux path, strict resume, and a tiny CPU smoke."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from training.qam_aware_v3_3_trainer import QAMAwareV33Trainer
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
        rng = np.random.default_rng(np.random.SeedSequence([331, epoch, index]))
        values = torch.tensor(rng.normal(size=4), dtype=torch.float32)
        return values, int((index + epoch) % 2)


class TinyV33Net(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Linear(8, 2))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)

    def forward_with_aux(self, inputs: torch.Tensor):
        logits = self.network(inputs)
        return logits, {"residual": torch.zeros_like(logits)}

    def forward_domain(self, inputs: torch.Tensor, *, hardware_sim: bool) -> torch.Tensor:
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
        "residual_penalty_weight": 0.0,
        "family_aux_loss_weight": 0.0,
        "domain_consistency": {"enabled": False, "weight": 0.0, "mechanism": "consistency"},
    }
    training.update(overrides)
    return training


def _make_trainer(root: Path, seed: int = 77, **training_overrides: object) -> QAMAwareV33Trainer:
    config = {
        "seed": seed,
        "training": _training(**training_overrides),
        "model": {"family_aux": {"enabled": False}},
    }
    return QAMAwareV33Trainer(
        TinyV33Net(),
        torch.device("cpu"),
        config,
        ensure_output_dirs(root),
        ["zero", "one"],
    )


def _loaders(seed: int):
    train_set = EpochDataset(32, "train")
    val_set = EpochDataset(16, "validation")
    generator = torch.Generator().manual_seed(seed)
    return (
        DataLoader(train_set, batch_size=8, shuffle=True, generator=generator),
        DataLoader(val_set, batch_size=8, shuffle=False),
    )


def _nested_equal(left, right) -> bool:
    if torch.is_tensor(left):
        return bool(torch.equal(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_nested_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_nested_equal(a, b) for a, b in zip(left, right))
    return left == right


def test_cpu_smoke_produces_finite_loss_and_best_checkpoint(tmp_path: Path) -> None:
    set_seed(77)
    trainer = _make_trainer(tmp_path)
    train_loader, val_loader = _loaders(77)
    history = trainer.fit(train_loader, val_loader)
    assert history
    assert all(np.isfinite(row["train_loss"]) and np.isfinite(row["val_loss"]) for row in history)
    best = torch.load(tmp_path / "checkpoints" / "best.pt", map_location="cpu", weights_only=False)
    assert best["checkpoint_metric"] == "val_macro_f1"
    assert best["checkpoint_mode"] == "max"


def test_domain_consistency_loss_is_finite(tmp_path: Path) -> None:
    set_seed(77)
    trainer = _make_trainer(
        tmp_path, domain_consistency={"enabled": True, "weight": 1.0, "mechanism": "consistency"}
    )
    assert trainer.domain_enabled is True
    train_loader, val_loader = _loaders(77)
    history = trainer.fit(train_loader, val_loader)
    assert all(np.isfinite(row["train_loss"]) for row in history)


def test_strict_resume_matches_continuous(tmp_path: Path) -> None:
    set_seed(77)
    continuous = _make_trainer(tmp_path / "continuous")
    continuous_train, continuous_val = _loaders(77)
    continuous_history = continuous.fit(continuous_train, continuous_val)

    set_seed(77)
    split = _make_trainer(tmp_path / "split")
    split_train, split_val = _loaders(77)
    first_history = split.fit(split_train, split_val, stop_after_epoch=2)

    set_seed(77)
    resumed = _make_trainer(tmp_path / "split")
    resumed_train, resumed_val = _loaders(77)
    resumed_history = resumed.fit(
        resumed_train, resumed_val, resume_path=tmp_path / "split" / "checkpoints" / "last.pt"
    )

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


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_cuda_smoke_forward_backward_is_finite() -> None:
    """A tiny forward/backward on device so the AutoDL GPU path is exercised once."""
    device = torch.device("cuda")
    model = TinyV33Net().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    inputs = torch.randn(32, 4, device=device)
    labels = torch.randint(0, 2, (32,), device=device)
    logits, _ = model.forward_with_aux(inputs)
    loss = nn.functional.cross_entropy(logits, labels)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    assert torch.isfinite(loss).all()
    assert logits.is_cuda
