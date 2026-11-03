"""Deterministic robustness curriculum for the V1.2 data-only candidate.

V1.2 deliberately keeps the V1.1 signal, label, model, and deployment
contracts frozen.  Only the *training* channel distribution changes.  A
separate RNG selects a channel profile so an A/B variant sees the exact same
underlying clean waveform for a given ``(seed, split, epoch, index)``.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from channel.channel_pipeline import ChannelPipeline
from datasets.ad_amr_dataset import SAMPLE_ID_STRIDE, collate_ad_amr
from datasets.ad_amr_v1_1_dataset import assert_v1_1_signal_contract
from datasets.modulation_generator import generate_iq

PROFILE_RNG_TAG = 0x563132  # ASCII-like stable tag for "V12".


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _normalise_weights(weights: dict[str, float], names: tuple[str, ...]) -> np.ndarray:
    unknown = set(weights) - set(names)
    if unknown:
        raise ValueError(f"unknown robustness profiles in weights: {sorted(unknown)}")
    values = np.asarray([float(weights.get(name, 0.0)) for name in names], dtype=np.float64)
    if not np.isfinite(values).all() or np.any(values < 0.0) or float(values.sum()) <= 0.0:
        raise ValueError("profile weights must be finite, non-negative, and have positive sum")
    return values / values.sum()


class ADAMRV12Dataset(Dataset):
    """V1.1-compatible IQ pairs with training-only channel-profile routing."""

    def __init__(
        self,
        num_samples: int,
        signal_config: dict[str, Any],
        channel_config: dict[str, Any],
        robustness_config: dict[str, Any] | None = None,
        seed: int = 2026,
        split: str = "ad_amr_v1_2_train",
        fixed_snr_db: float | None = None,
        snr_values: list[float] | None = None,
    ) -> None:
        assert_v1_1_signal_contract(signal_config)
        if "blind" in str(split).lower():
            raise RuntimeError("final blind data may not be instantiated by V1.2 preparation/training")
        self.num_samples = int(num_samples)
        self.signal_config = copy.deepcopy(signal_config)
        self.channel_config = copy.deepcopy(channel_config)
        self.robustness_config = copy.deepcopy(robustness_config or {})
        self.seed = int(seed)
        self.split = str(split)
        self.split_code = int.from_bytes(
            hashlib.blake2s(self.split.encode("utf-8"), digest_size=4).digest(), "little"
        )
        self.sample_id_base = self.split_code * SAMPLE_ID_STRIDE
        self.fixed_snr_db = fixed_snr_db
        self.snr_values = [float(value) for value in snr_values] if snr_values else None
        self.modulations = [str(name).upper() for name in signal_config["modulations"]]
        self.is_train_split = "train" in self.split.lower()
        self.epoch = 0

        profile_overrides = self.robustness_config.get("profiles", {})
        self.profile_names = ("base", *tuple(str(name) for name in profile_overrides))
        self.channels: dict[str, ChannelPipeline] = {
            "base": ChannelPipeline(self.channel_config, signal_config["sample_rate"]),
        }
        for name, overrides in profile_overrides.items():
            merged = _deep_merge(self.channel_config, overrides)
            self.channels[str(name)] = ChannelPipeline(merged, signal_config["sample_rate"])

        start = self.robustness_config.get("start_weights", {"base": 1.0})
        target = self.robustness_config.get("target_weights", start)
        self.start_weights = _normalise_weights(start, self.profile_names)
        self.target_weights = _normalise_weights(target, self.profile_names)
        self.enabled = bool(self.robustness_config.get("enabled", False)) and self.is_train_split
        self.warmup_epochs = max(0, int(self.robustness_config.get("warmup_epochs", 0)))
        self.ramp_epochs = max(1, int(self.robustness_config.get("ramp_epochs", 1)))

    def __len__(self) -> int:
        return self.num_samples

    def set_epoch(self, epoch: int) -> None:
        if self.is_train_split:
            self.epoch = int(epoch)

    def profile_probabilities(self, epoch: int | None = None) -> dict[str, float]:
        if not self.enabled:
            return {name: float(name == "base") for name in self.profile_names}
        value = self.epoch if epoch is None else int(epoch)
        progress = np.clip((value - self.warmup_epochs) / self.ramp_epochs, 0.0, 1.0)
        weights = (1.0 - progress) * self.start_weights + progress * self.target_weights
        weights /= weights.sum()
        return dict(zip(self.profile_names, (float(item) for item in weights)))

    def _profile_for(self, index: int, epoch_key: int) -> str:
        probabilities = self.profile_probabilities(epoch_key)
        names = tuple(probabilities)
        selector = np.random.default_rng(np.random.SeedSequence([
            self.seed, self.split_code, epoch_key, int(index), PROFILE_RNG_TAG,
        ]))
        return str(selector.choice(names, p=[probabilities[name] for name in names]))

    def __getitem__(self, index: int) -> dict[str, Any]:
        epoch_key = self.epoch if self.is_train_split else 0
        rng = np.random.default_rng(np.random.SeedSequence([
            self.seed, self.split_code, epoch_key, int(index),
        ]))
        if self.snr_values and self.fixed_snr_db is None:
            combination = int(index) % (len(self.modulations) * len(self.snr_values))
            label = combination % len(self.modulations)
            assigned_snr = self.snr_values[combination // len(self.modulations)]
        else:
            label = int(index) % len(self.modulations)
            assigned_snr = self.fixed_snr_db

        clean, _ = generate_iq(self.modulations[label], self.signal_config, rng)
        profile = self._profile_for(index, epoch_key)
        noisy, channel_metadata = self.channels[profile](clean, rng, snr_db=assigned_snr)

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
            "channel_profile": profile,
            "channel_effects": tuple(channel_metadata.get("effects", ())),
        }


def collate_ad_amr_v1_2(batch: list[dict[str, Any]]) -> dict[str, Any]:
    result = collate_ad_amr(batch)
    result["channel_profile"] = [str(item["channel_profile"]) for item in batch]
    result["channel_effects"] = [tuple(item["channel_effects"]) for item in batch]
    return result


__all__ = ["ADAMRV12Dataset", "collate_ad_amr_v1_2"]
