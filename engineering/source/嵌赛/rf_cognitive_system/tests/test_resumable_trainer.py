from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from training.resumable_trainer import CHECKPOINT_VERSION, ResumableTrainer
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


def make_config() -> dict:
    return {
        "seed": 77,
        "training": {
            "epochs": 4,
            "batch_size": 8,
            "optimizer": "AdamW",
            "learning_rate": 0.002,
            "weight_decay": 0.0001,
            "scheduler": "cosine",
            "early_stopping_patience": 20,
            "min_delta": 0.0,
        },
    }


def run(root: Path, stop: int | None = None, resume: Path | None = None):
    config = make_config()
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
    return trainer, history, train_set


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


def test_strict_resume_matches_continuous_training(tmp_path: Path) -> None:
    continuous, continuous_history, continuous_dataset = run(tmp_path / "continuous")
    _, first_history, _ = run(tmp_path / "split", stop=2)
    resumed, resumed_history, resumed_dataset = run(
        tmp_path / "split", resume=tmp_path / "split" / "checkpoints" / "last.pt"
    )

    assert [row["epoch"] for row in first_history] == [1, 2]
    assert [row["epoch"] for row in resumed_history] == [1, 2, 3, 4]
    assert [row["learning_rate"] for row in continuous_history] == [
        row["learning_rate"] for row in resumed_history
    ]
    for left, right in zip(continuous_history, resumed_history):
        for key in ("train_loss", "train_accuracy", "val_loss", "val_accuracy"):
            assert left[key] == right[key]
    assert continuous_dataset.epoch == resumed_dataset.epoch == 4
    assert_nested_equal(continuous.model.state_dict(), resumed.model.state_dict())
    assert_nested_equal(continuous.optimizer.state_dict(), resumed.optimizer.state_dict())
    assert_nested_equal(continuous.scheduler.state_dict(), resumed.scheduler.state_dict())

    checkpoint = torch.load(
        tmp_path / "split" / "checkpoints" / "last.pt", map_location="cpu", weights_only=False
    )
    assert checkpoint["checkpoint_version"] == CHECKPOINT_VERSION
    assert checkpoint["epoch"] == 4
    assert checkpoint["next_epoch"] == 5
    assert checkpoint["dataset_state"] == {"train_epoch": 4, "next_epoch": 5, "split": "train"}
    assert set(checkpoint["rng_state"]) >= {"python", "numpy", "torch_cpu"}
    assert checkpoint["scheduler_state"] is not None
    assert checkpoint["best_epoch"] is not None
    assert "stale_epochs" in checkpoint["early_stopping_state"]
