"""Clean/noisy IQ-pair dataset for the AD-AMR denoising+classification task.

The AD-AMR loss needs the *same* signal instance in two forms — the clean
transmitted waveform (denoising target for the P1 variant) and the channel-
impaired received waveform (network input) — plus the label, the assigned SNR,
and a stable, non-colliding sample id.

Reproducibility mirrors ``model_v3_3/datasets/synthetic_dataset.py``: the RNG for
sample ``index`` is ``SeedSequence([seed, split_code, epoch, index])``, so a given
``(seed, split, index)`` always yields the byte-identical clean and noisy records.
``split_code`` is ``blake2s(split_string)``; distinct split strings therefore yield
distinct sample-id ranges (no train/val/test sample_id overlap).
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from channel.channel_pipeline import ChannelPipeline
from datasets.modulation_generator import generate_iq

SAMPLE_ID_STRIDE = 1_000_000


class ADAMRPairDataset(Dataset):
    def __init__(
        self,
        num_samples: int,
        signal_config: dict[str, Any],
        channel_config: dict[str, Any] | None = None,
        seed: int = 2026,
        split: str = "train",
        fixed_snr_db: float | None = None,
        snr_values: list[float] | None = None,
    ) -> None:
        self.num_samples = int(num_samples)
        self.signal_config = signal_config
        self.channel_config = channel_config
        self.seed = int(seed)
        self.split = str(split)
        self.split_code = int.from_bytes(
            hashlib.blake2s(self.split.encode("utf-8"), digest_size=4).digest(), "little"
        )
        self.sample_id_base = self.split_code * SAMPLE_ID_STRIDE
        self.fixed_snr_db = fixed_snr_db
        self.snr_values = [float(v) for v in snr_values] if snr_values else None
        self.modulations = [name.upper() for name in signal_config["modulations"]]
        self.class_to_index = {name: i for i, name in enumerate(self.modulations)}
        self.is_train_split = "train" in self.split
        self.epoch = 0
        self.channel = ChannelPipeline(channel_config, signal_config["sample_rate"]) if channel_config else None

    def __len__(self) -> int:
        return self.num_samples

    def set_epoch(self, epoch: int) -> None:
        if self.is_train_split:
            self.epoch = int(epoch)

    def __getitem__(self, index: int) -> dict[str, Any]:
        epoch_key = self.epoch if self.is_train_split else 0
        seed_key = [self.seed, self.split_code, epoch_key, int(index)]
        rng = np.random.default_rng(np.random.SeedSequence(seed_key))

        if self.snr_values and self.fixed_snr_db is None:
            combination = int(index) % (len(self.modulations) * len(self.snr_values))
            label = combination % len(self.modulations)
            assigned_snr = self.snr_values[combination // len(self.modulations)]
        else:
            label = int(index) % len(self.modulations)
            assigned_snr = self.fixed_snr_db

        modulation = self.modulations[label]
        clean, signal_metadata = generate_iq(modulation, self.signal_config, rng)
        if self.channel is not None:
            noisy, channel_metadata = self.channel(clean, rng, snr_db=assigned_snr)
        else:
            noisy, channel_metadata = clean, {"effects": []}

        def to_tensor(iq: np.ndarray) -> torch.Tensor:
            return torch.from_numpy(np.stack((iq.real, iq.imag)).astype(np.float32))

        return {
            "clean_iq": to_tensor(clean),
            "noisy_iq": to_tensor(noisy),
            "label": int(label),
            "snr_db": float(assigned_snr),
            "sample_id": int(self.sample_id_base + int(index)),
            "split": self.split,
            "seed": self.seed,
        }


def collate_ad_amr(batch: list[dict[str, Any]]) -> dict[str, Any]:
    """Collate ADAMRPairDataset records into batched tensors."""
    return {
        "clean_iq": torch.stack([b["clean_iq"] for b in batch]),
        "noisy_iq": torch.stack([b["noisy_iq"] for b in batch]),
        "label": torch.tensor([b["label"] for b in batch], dtype=torch.long),
        "snr_db": torch.tensor([b["snr_db"] for b in batch], dtype=torch.float32),
        "sample_id": torch.tensor([b["sample_id"] for b in batch], dtype=torch.int64),
        "split": [b["split"] for b in batch],
        "seed": [b["seed"] for b in batch],
    }
