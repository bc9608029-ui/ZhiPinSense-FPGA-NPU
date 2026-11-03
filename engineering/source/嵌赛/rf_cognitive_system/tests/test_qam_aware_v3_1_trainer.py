"""Direct checks of the V3.1 checkpoint-selection and early-stop fixes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
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
        rng = np.random.default_rng(np.random.SeedSequence([123, epoch, index]))
        values = torch.tensor(rng.normal(size=4), dtype=torch.float32)
        return values, int((index + epoch) % 2)


class TinyNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Dropout(0.2), nn.Linear(8, 2))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


class ConstantNet(nn.Module):
    """Zero-weight network: loss/accuracy are exactly constant every epoch.

    ``scale`` is a zero-valued trainable parameter so ``loss.backward()`` has a
    grad_fn to work through, while the output (and therefore the monitor) stays
    exactly constant.
    """

    def __init__(self) -> None:
        super().__init__()
        self.fc = nn.Linear(4, 2)
        self.fc.weight.data.zero_()
        self.fc.bias.data.zero_()
        for parameter in self.fc.parameters():
            parameter.requires_grad_(False)
        self.scale = nn.Parameter(torch.zeros(1))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.fc(inputs) * self.scale


def _config(**training_overrides: object) -> dict:
    training = {
        "epochs": 6,
        "batch_size": 8,
        "optimizer": "AdamW",
        "learning_rate": 0.002,
        "weight_decay": 0.0001,
        "scheduler": "cosine",
        "early_stopping_patience": 1,
        "min_delta": 0.0,
    }
    training.update(training_overrides)
    return {"seed": 55, "training": training}


def _run(model: nn.Module, config: dict, root: Path) -> tuple[ResumableTrainer, list[dict]]:
    set_seed(config["seed"])
    train_set = EpochDataset(32, "train")
    val_set = EpochDataset(16, "validation")
    generator = torch.Generator().manual_seed(config["seed"])
    train_loader = DataLoader(train_set, batch_size=8, shuffle=True, generator=generator)
    val_loader = DataLoader(val_set, batch_size=8, shuffle=False)
    trainer = ResumableTrainer(
        model, torch.device("cpu"), config, ensure_output_dirs(root), ["zero", "one"]
    )
    history = trainer.fit(train_loader, val_loader)
    return trainer, history


def test_checkpoint_selection_tracks_macro_f1_maximum(tmp_path: Path) -> None:
    config = _config(checkpoint_metric="val_macro_f1", checkpoint_mode="max")
    _, history = _run(TinyNet(), config, tmp_path)
    assert history
    best = torch.load(tmp_path / "checkpoints" / "best.pt", map_location="cpu", weights_only=False)
    f1_by_epoch = {row["epoch"]: row["val_macro_f1"] for row in history}
    expected_epoch = max(f1_by_epoch, key=f1_by_epoch.get)
    assert best["best_epoch"] == expected_epoch
    assert abs(float(best["best_monitor_value"]) - f1_by_epoch[expected_epoch]) < 1e-9
    assert best["checkpoint_metric"] == "val_macro_f1"
    assert best["checkpoint_mode"] == "max"


def test_minimum_epochs_floor_delays_early_stopping(tmp_path: Path) -> None:
    config = _config(minimum_epochs_before_stopping=4)
    _, history = _run(ConstantNet(), config, tmp_path)
    # patience=1 would stop at epoch 2 without the floor; the floor holds it to 4.
    assert [row["epoch"] for row in history] == [1, 2, 3, 4]
