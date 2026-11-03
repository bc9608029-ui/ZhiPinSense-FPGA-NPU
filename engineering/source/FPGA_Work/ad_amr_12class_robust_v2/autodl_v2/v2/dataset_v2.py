"""V2 pair dataset: V1 generation + V2 augmentation + SNR curriculum.

Reproducibility is inherited from V1: the RNG for sample ``index`` is
``SeedSequence([seed, split_code, epoch, index])``.  With ``curriculum="none"``
and no augmentation the emitted records are byte-identical to V1's
``ADAMRPairDataset`` (Phase 1 baseline reproduction).  The augmentation stage
uses a distinct, clearly-tagged seed so it can never collide with V1's stream.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from datasets.ad_amr_dataset import ADAMRPairDataset, SAMPLE_ID_STRIDE
from datasets.modulation_generator import generate_iq
from v2.augmentation import V2Augmentor
from v2.curriculum import active_snr_values

# AUGMENTATION_RNG_TAG: distinct discriminator in the SeedSequence so V2's
# post-channel augmentation RNG can never collide with V1's 4-element seed.
AUGMENTATION_RNG_TAG = 0x5EED


class V2Dataset(ADAMRPairDataset):
    def __init__(
        self,
        num_samples: int,
        signal_config: dict[str, Any],
        channel_config: dict[str, Any] | None = None,
        seed: int = 2026,
        split: str = "train",
        fixed_snr_db: float | None = None,
        snr_values: list[float] | None = None,
        augmentor: V2Augmentor | None = None,
        curriculum: str = "none",
        total_epochs: int = 100,
    ) -> None:
        super().__init__(num_samples, signal_config, channel_config, seed, split,
                         fixed_snr_db=fixed_snr_db, snr_values=snr_values)
        self.augmentor = augmentor
        self.curriculum = str(curriculum)
        self.total_epochs = int(total_epochs)
        self.full_snr_values = list(self.snr_values) if self.snr_values else None

    def _active_snr(self) -> list[float] | None:
        if not self.is_train_split:
            return self.full_snr_values
        if self.full_snr_values is None or self.fixed_snr_db is not None:
            return None
        return active_snr_values(self.curriculum, self.full_snr_values,
                                 int(self.epoch), self.total_epochs)

    def __getitem__(self, index: int) -> dict[str, Any]:
        epoch_key = self.epoch if self.is_train_split else 0
        rng = np.random.default_rng(
            np.random.SeedSequence([self.seed, self.split_code, epoch_key, int(index)])
        )
        active = self._active_snr()
        if self.fixed_snr_db is not None:
            label = int(index) % len(self.modulations)
            assigned_snr = self.fixed_snr_db
        elif active is not None and len(active) > 0:
            combination = int(index) % (len(self.modulations) * len(active))
            label = combination % len(self.modulations)
            assigned_snr = active[combination // len(self.modulations)]
        else:
            label = int(index) % len(self.modulations)
            assigned_snr = None

        modulation = self.modulations[label]
        clean, _ = generate_iq(modulation, self.signal_config, rng)
        if self.channel is not None:
            noisy, _ = self.channel(clean, rng, snr_db=assigned_snr)
        else:
            noisy = clean

        if self.augmentor is not None and self.is_train_split:
            aug_rng = np.random.default_rng(
                np.random.SeedSequence(
                    [self.seed, self.split_code, epoch_key, int(index), AUGMENTATION_RNG_TAG]
                )
            )
            noisy = self.augmentor(noisy.astype(np.complex64), aug_rng)

        def to_tensor(iq: np.ndarray) -> torch.Tensor:
            return torch.from_numpy(np.stack((iq.real, iq.imag)).astype(np.float32))

        return {
            "clean_iq": to_tensor(clean),
            "noisy_iq": to_tensor(noisy),
            "label": int(label),
            "snr_db": float(assigned_snr) if assigned_snr is not None else 0.0,
            "sample_id": int(self.sample_id_base + int(index)),
            "split": self.split,
            "seed": self.seed,
        }


__all__ = ["V2Dataset", "SAMPLE_ID_STRIDE"]
