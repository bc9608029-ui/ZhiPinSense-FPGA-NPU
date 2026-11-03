"""Strict-resume equivalence under V3.1's macro-F1 / max selection policy."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from training.resumable_trainer import ResumableTrainer
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
        rng = np.random.default_rng(np.random.SeedSequence([991, epoch, index]))
        values = torch.tensor(rng.normal(size=4), dtype=torch.float32)
        return values, int((index + epoch) % 2)


class TinyDropoutNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Dropout(0.2), nn.Linear(8, 2))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


def make_config(**training_overrides: object) -> dict:
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
    }
    training.update(training_overrides)
    return {"seed": 77, "training": training}


def run(root: Path, *, stop: int | None = None, resume: Path | None = None, config: dict | None = None):
    config = config or make_config()
    set_seed(config["seed"])
    train_set = EpochDataset(32, "train")
    val_set = EpochDataset(16, "validation")
    generator = torch.Generator().manual_seed(config["seed"])
    train_loader = DataLoader(train_set, batch_size=8, shuffle=True, generator=generator)
    val_loader = DataLoader(val_set, batch_size=8, shuffle=False)
    trainer = ResumableTrainer(
        TinyDropoutNet(), torch.device("cpu"), config, ensure_output_dirs(root), ["zero", "one"]
    )
    history = trainer.fit(train_loader, val_loader, resume_path=resume, stop_after_epoch=stop)
    return trainer, history


def assert_nested_equal(left, right) -> None:
    if torch.is_tensor(left):
        assert torch.equal(left, right)
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            assert_nested_equal(left[key], right[key])
    elif isinstance(left, list):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            assert_nested_equal(a, b)
    else:
        assert left == right


def _final_checkpoint(root: Path) -> dict:
    return torch.load(root / "checkpoints" / "last.pt", map_location="cpu", weights_only=False)


def test_strict_resume_macro_f1_matches_continuous(tmp_path: Path) -> None:
    continuous, continuous_history = run(tmp_path / "continuous")
    _, first_history = run(tmp_path / "split", stop=2)
    resumed, resumed_history = run(
        tmp_path / "split", resume=tmp_path / "split" / "checkpoints" / "last.pt"
    )

    assert [row["epoch"] for row in first_history] == [1, 2]
    assert [row["epoch"] for row in resumed_history] == [1, 2, 3, 4]
    assert [row["epoch"] for row in continuous_history] == [1, 2, 3, 4]

    # History must match on every field except wall-clock training time.
    for left, right in zip(continuous_history, resumed_history):
        assert left.keys() == right.keys()
        for key in left:
            if key == "training_time_sec":
                continue
            assert left[key] == right[key], f"history field {key!r} diverged"

    assert_nested_equal(continuous.model.state_dict(), resumed.model.state_dict())
    assert_nested_equal(continuous.optimizer.state_dict(), resumed.optimizer.state_dict())
    assert_nested_equal(continuous.scheduler.state_dict(), resumed.scheduler.state_dict())

    continuous_ckpt = _final_checkpoint(tmp_path / "continuous")
    resumed_ckpt = _final_checkpoint(tmp_path / "split")
    assert continuous_ckpt["best_epoch"] == resumed_ckpt["best_epoch"]
    assert continuous_ckpt["best_monitor_value"] == resumed_ckpt["best_monitor_value"]
    assert (
        continuous_ckpt["early_stopping_state"]["stale_epochs"]
        == resumed_ckpt["early_stopping_state"]["stale_epochs"]
    )
    assert continuous_ckpt["next_epoch"] == resumed_ckpt["next_epoch"] == 5
    assert continuous_ckpt["checkpoint_metric"] == "val_macro_f1"
    assert continuous_ckpt["checkpoint_mode"] == "max"


def test_resume_rejects_selection_policy_change(tmp_path: Path) -> None:
    run(tmp_path / "policy", stop=2)
    last_pt = tmp_path / "policy" / "checkpoints" / "last.pt"
    mismatched = make_config(checkpoint_metric="val_loss", checkpoint_mode="min")
    with pytest.raises(RuntimeError, match="selection policy changed"):
        run(tmp_path / "policy", resume=last_pt, config=mismatched)
