"""AD-AMR data wrapper tests: determinism + sample-id isolation."""

from __future__ import annotations

import torch

from datasets.ad_amr_dataset import ADAMRPairDataset
from training.utils import load_yaml


def _config() -> dict:
    return load_yaml("configs/ad_amr_v1.yaml")


def _dataset(split: str, num: int) -> ADAMRPairDataset:
    cfg = _config()
    return ADAMRPairDataset(num, cfg["signal"], cfg["channel"], 2026, split,
                            snr_values=[-20.0, -10.0, 0.0, 10.0, 20.0])


def test_deterministic_reproducibility() -> None:
    a = _dataset("ad_amr_train", 16)
    b = _dataset("ad_amr_train", 16)
    for index in range(8):
        ra, rb = a[index], b[index]
        assert torch.equal(ra["clean_iq"], rb["clean_iq"])
        assert torch.equal(ra["noisy_iq"], rb["noisy_iq"])
        assert ra["label"] == rb["label"]
        assert ra["snr_db"] == rb["snr_db"]
        assert ra["sample_id"] == rb["sample_id"]


def test_clean_and_noisy_same_signal_label() -> None:
    ds = _dataset("ad_amr_train", 32)
    for index in range(8):
        rec = ds[index]
        assert rec["clean_iq"].shape == (2, 1024)
        assert rec["noisy_iq"].shape == (2, 1024)
        # AWGN channel: noisy differs from clean for the same signal instance.
        assert not torch.equal(rec["clean_iq"], rec["noisy_iq"])
        assert rec["split"] == "ad_amr_train"
        assert rec["seed"] == 2026


def test_sample_id_no_overlap_across_splits() -> None:
    train = _dataset("ad_amr_train", 64)
    val = _dataset("ad_amr_validation", 32)
    test = _dataset("ad_amr_test", 32)
    ids = {}
    for name, ds in (("train", train), ("val", val), ("test", test)):
        ids[name] = {ds[i]["sample_id"] for i in range(len(ds))}
    assert not (ids["train"] & ids["val"])
    assert not (ids["train"] & ids["test"])
    assert not (ids["val"] & ids["test"])


def test_label_maps_to_class_order() -> None:
    ds = _dataset("ad_amr_train", 64)
    cfg = _config()
    classes = [c.upper() for c in cfg["signal"]["modulations"]]
    assert classes == ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    # Balanced modulo mapping: label = index % 8.
    for index in range(16):
        assert ds[index]["label"] == index % 8
