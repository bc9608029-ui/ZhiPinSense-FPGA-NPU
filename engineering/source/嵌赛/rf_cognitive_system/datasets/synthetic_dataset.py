"""On-the-fly balanced synthetic IQ dataset."""

from __future__ import annotations

from typing import Any
import hashlib

import numpy as np
import torch
from torch.utils.data import Dataset

from channel.channel_pipeline import ChannelPipeline
from datasets.modulation_generator import generate_iq


class SyntheticModulationDataset(Dataset):
    def __init__(
        self,
        num_samples: int,
        signal_config: dict[str, Any],
        channel_config: dict[str, Any] | None = None,
        seed: int = 2026,
        split: str = "train",
        return_metadata: bool = False,
        fixed_snr_db: float | None = None,
        snr_values: list[float] | None = None,
    ) -> None:
        self.num_samples = int(num_samples)
        self.signal_config = signal_config
        self.channel_config = channel_config
        self.seed = int(seed)
        self.split = str(split)
        self.split_code = int.from_bytes(hashlib.blake2s(self.split.encode("utf-8"), digest_size=4).digest(), "little")
        self.return_metadata = return_metadata
        self.fixed_snr_db = fixed_snr_db
        self.snr_values = [float(value) for value in snr_values] if snr_values else None
        self.modulations = [name.upper() for name in signal_config["modulations"]]
        self.class_to_index = {name: index for index, name in enumerate(self.modulations)}
        self.epoch = 0
        self.channel = ChannelPipeline(channel_config, signal_config["sample_rate"]) if channel_config else None

    def __len__(self) -> int:
        return self.num_samples

    def set_epoch(self, epoch: int) -> None:
        # Evaluation records remain immutable even if a caller invokes set_epoch.
        if self.split == "train":
            self.epoch = int(epoch)

    def __getitem__(self, index: int):
        epoch_key = self.epoch if self.split == "train" else 0
        seed_key = [self.seed, self.split_code, epoch_key, int(index)]
        # SeedSequence prevents arithmetic key overlap across splits and epochs.
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
            iq, channel_metadata = self.channel(clean, rng, snr_db=assigned_snr)
        else:
            iq, channel_metadata = clean, {"effects": []}
        tensor = torch.from_numpy(np.stack((iq.real, iq.imag)).astype(np.float32))
        if self.return_metadata:
            metadata = {
                "index": int(index),
                "seed_key": seed_key,
                "split": self.split,
                "epoch": epoch_key,
                "assigned_snr_db": assigned_snr,
                "signal": signal_metadata,
                "channel": channel_metadata,
            }
            return tensor, label, metadata
        return tensor, label
