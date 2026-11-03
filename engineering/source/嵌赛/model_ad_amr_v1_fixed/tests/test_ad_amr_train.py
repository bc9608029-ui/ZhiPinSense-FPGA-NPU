"""AD-AMR training tests: overfit, smoke, reload/resume, NaN/Inf guard."""

from __future__ import annotations

import random

import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_dataset import ADAMRPairDataset, collate_ad_amr
from models.ad_amr_net import build_ad_amr_model
from training.ad_amr_trainer import ADAMRTrainer
from training.utils import ensure_output_dirs, load_yaml, set_seed


def _tiny_config(tmp_path, variant: str = "P0") -> dict:
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    cfg["output_root"] = str(tmp_path / "outputs")
    cfg["training"]["loss"]["variant"] = variant
    cfg["device"] = "cpu"
    return cfg


def _loaders(cfg: dict, train_n: int, val_n: int, seed: int = 2026):
    signal, channel = cfg["signal"], cfg["channel"]
    snr = [float(v) for v in cfg["dataset"]["snr_values"]]
    train_set = ADAMRPairDataset(train_n, signal, channel, seed, "ad_amr_train", snr_values=snr)
    val_set = ADAMRPairDataset(val_n, signal, channel, seed, "ad_amr_validation", snr_values=snr)
    bs = int(cfg["training"]["batch_size"])
    train_loader = DataLoader(train_set, batch_size=bs, shuffle=True, collate_fn=collate_ad_amr,
                              generator=torch.Generator().manual_seed(seed))
    val_loader = DataLoader(val_set, batch_size=bs, shuffle=False, collate_fn=collate_ad_amr)
    return train_loader, val_loader


def test_single_batch_overfit(tmp_path) -> None:
    cfg = _tiny_config(tmp_path)
    set_seed(2026)
    classes = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    paths = ensure_output_dirs(cfg["output_root"])
    model = build_ad_amr_model(8, **cfg["model"])
    trainer = ADAMRTrainer(model, torch.device("cpu"), cfg, paths, classes)
    train_loader, val_loader = _loaders(cfg, 16, 8)
    history = trainer.fit(train_loader, val_loader, stop_after_epoch=1)
    assert len(history) == 1
    assert np.isfinite(history[0]["train_loss"])


def test_two_epoch_smoke_checkpoints(tmp_path) -> None:
    cfg = _tiny_config(tmp_path)
    set_seed(2026)
    classes = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    paths = ensure_output_dirs(cfg["output_root"])
    model = build_ad_amr_model(8, **cfg["model"])
    trainer = ADAMRTrainer(model, torch.device("cpu"), cfg, paths, classes)
    train_loader, val_loader = _loaders(cfg, 32, 16)
    history = trainer.fit(train_loader, val_loader, stop_after_epoch=2)
    assert [row["epoch"] for row in history] == [1, 2]
    assert all(np.isfinite(row["train_loss"]) and np.isfinite(row["val_loss"]) for row in history)
    assert (paths["checkpoints"] / "best.pt").exists()
    assert (paths["checkpoints"] / "last.pt").exists()


def test_reload_and_resume(tmp_path) -> None:
    cfg = _tiny_config(tmp_path)
    set_seed(2026)
    classes = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    paths = ensure_output_dirs(cfg["output_root"])
    model = build_ad_amr_model(8, **cfg["model"])
    trainer = ADAMRTrainer(model, torch.device("cpu"), cfg, paths, classes)
    train_loader, val_loader = _loaders(cfg, 32, 16)
    trainer.fit(train_loader, val_loader, stop_after_epoch=1)
    saved_epoch = trainer.history[-1]["epoch"]
    saved_params = {k: v.clone() for k, v in model.state_dict().items()}
    saved_rng = torch.get_rng_state().clone()

    # Perturb RNG and build a fresh trainer, then resume.
    random.seed(999)
    np.random.seed(999)
    torch.manual_seed(999)
    fresh_model = build_ad_amr_model(8, **cfg["model"])
    fresh = ADAMRTrainer(fresh_model, torch.device("cpu"), cfg, paths, classes)
    train_loader2, val_loader2 = _loaders(cfg, 32, 16)
    train_loader2.generator.manual_seed(999)
    resumed_epoch = fresh.load_resume(paths["checkpoints"] / "last.pt", train_loader2)
    assert resumed_epoch == saved_epoch
    assert [row["epoch"] for row in fresh.history] == [saved_epoch]
    for k, v in saved_params.items():
        assert torch.equal(fresh.model.state_dict()[k], v), f"param {k} not restored"
    assert torch.equal(torch.get_rng_state(), saved_rng), "torch CPU RNG not restored"

    # Continue one more epoch; history grows cumulatively.
    history = fresh.fit(train_loader2, val_loader2, stop_after_epoch=1)
    assert [row["epoch"] for row in history] == [saved_epoch, saved_epoch + 1]


def test_strict_resume_matches_continuous_training(tmp_path) -> None:
    classes = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]

    continuous_cfg = _tiny_config(tmp_path / "continuous")
    set_seed(2026)
    continuous_paths = ensure_output_dirs(continuous_cfg["output_root"])
    continuous_model = build_ad_amr_model(8, **continuous_cfg["model"])
    continuous = ADAMRTrainer(
        continuous_model, torch.device("cpu"), continuous_cfg, continuous_paths, classes
    )
    train_c, val_c = _loaders(continuous_cfg, 32, 16)
    continuous.fit(train_c, val_c, stop_after_epoch=2)
    expected = {name: value.clone() for name, value in continuous_model.state_dict().items()}

    resumed_cfg = _tiny_config(tmp_path / "resumed")
    set_seed(2026)
    resumed_paths = ensure_output_dirs(resumed_cfg["output_root"])
    first_model = build_ad_amr_model(8, **resumed_cfg["model"])
    first = ADAMRTrainer(first_model, torch.device("cpu"), resumed_cfg, resumed_paths, classes)
    train_1, val_1 = _loaders(resumed_cfg, 32, 16)
    first.fit(train_1, val_1, stop_after_epoch=1)

    second_model = build_ad_amr_model(8, **resumed_cfg["model"])
    second = ADAMRTrainer(second_model, torch.device("cpu"), resumed_cfg, resumed_paths, classes)
    train_2, val_2 = _loaders(resumed_cfg, 32, 16, seed=2026)
    train_2.generator.manual_seed(999)
    second.load_resume(resumed_paths["checkpoints"] / "last.pt", train_2)
    second.fit(train_2, val_2, stop_after_epoch=1)

    assert [row["epoch"] for row in second.history] == [1, 2]
    for name, value in expected.items():
        assert torch.equal(second_model.state_dict()[name], value), name


def test_nan_inf_guard_raises(tmp_path) -> None:
    cfg = _tiny_config(tmp_path)
    set_seed(2026)
    classes = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    paths = ensure_output_dirs(cfg["output_root"])
    model = build_ad_amr_model(8, **cfg["model"])
    trainer = ADAMRTrainer(model, torch.device("cpu"), cfg, paths, classes)
    train_loader, _ = _loaders(cfg, 8, 4)
    # Corrupt a batch with NaN to force a non-finite loss; the trainer must raise,
    # never silently swallow.
    batch = next(iter(train_loader))
    batch["noisy_iq"][0, 0, 0] = float("nan")
    model.train()
    with pytest.raises(RuntimeError):
        trainer._train_one_epoch([batch], epoch=1)
